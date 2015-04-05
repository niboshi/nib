#!/usr/bin/env python
# -*- mode:python; indent-tabs-mode:t; python-indent:4 -*-

import sys
import subprocess
import os
import time
import shutil
import tempfile
import io
import re
import curses
import fcntl
import mediainfo
import argparse
import threading
import Queue as queue

class VideoEncoderError(Exception): pass
class InsufficientOptionsError(VideoEncoderError): pass
class InsufficientOptionParametersError(VideoEncoderError): pass
class InvalidOptionError(VideoEncoderError): pass
class SubprocessFailedError(VideoEncoderError): pass
class CancelByUserError(VideoEncoderError): pass
class MediaFileNotSupportedError(VideoEncoderError): pass

class EncodeExecutor:
	def __init__(self, infile, outfile, mi, ffmpegCommonOpts):
		self.queue = queue.Queue()
		self.infile = infile
		self.outfile = outfile
		self.mi = mi
		self.ffmpegCommonOpts = ffmpegCommonOpts
		self.progress = 0
		self.proc = None
		pass

	def start(self):
		self.proc = self.startProcess()
		t = threading.Thread(target = self.asyncQueueThread, args=(self.proc.stderr,))
		t.daemon = True
		t.start()
		pass

	def asyncQueueThread(self, fp):
		q = self.queue
		buf = io.BytesIO()
		while True:
			data = fp.read(1)
			if len(data) == 0: break
			if data == "\n" or data == "\r":
				q.put(buf.getvalue())
				buf.truncate(0)
			else:
				buf.write(data)
	
	def getReturnCode(self):
		if self.proc == None: return None
		return self.proc.poll()

class VideoEncodeExecutor(EncodeExecutor):
	def __init__(self, infile, outfile, mi, ffmpegCommonOpts):
		EncodeExecutor.__init__(self, infile, outfile, mi, ffmpegCommonOpts)

		frameCount = mi['Video'].get('FrameCount', '')
		if frameCount == '':
			self.totalFrameCount = None
		else:
			self.totalFrameCount = int(frameCount)

	def startProcess(self):
		mi = self.mi
		width  = mi['Video']['Width']
		height = mi['Video']['Height']
		ffmpegVideoOpts = ['-an', '-f', 'rawvideo', '-vcodec', 'rawvideo', '-pix_fmt', 'yuv420p', '-']
		x264Opts = [ ]
		x264Opts += ['--output', self.outfile]
		x264Opts += ['-']
		if self.totalFrameCount != None:
			x264Opts += ['--frames', str(self.totalFrameCount)]
		x264Opts += ['--input-res', '%sx%s' % (width, height)]
		x264Opts += ['--crf', str(24.0)]
		x264Opts += ['--b-pyramid', 'none']       # forbid B-frames to be used as references (def:normal)
		x264Opts += ['--keyint', str(100)]           # max interval between keyframes (def:250)
		#x264Opts += ['--intra-refresh']           # disable IDR-frames and instead use macroblocks (def:off)
		
		# Motion Estimation
		# dia (fastest)  : simplest 4-pix search
		# hex (default)  : 6-pix search.
		# umh            : complex multi-hex pattern.
		# esa            : equivalent to blute-force
		# tesa (slowest) : a little bit better and slower
		#x264Opts += ['--me', 'hex']
		
		# RDO(Rate-distortion optimization) level
		# 0(faster)-11(slower) def:7
		#x264Opts += ['--subme', str(7)]
		
		# ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow, placebo
		# def:medium
		x264Opts += ['--preset', 'veryfast']
		
		ffmpegOpts = self.ffmpegCommonOpts + ffmpegVideoOpts
		poVideo1 = subprocess.Popen(
			["ffmpeg"] + ffmpegOpts,
			stdout = subprocess.PIPE,
			stderr = subprocess.PIPE,
			shell = False)
		poVideo  = subprocess.Popen(
			["x264"] + x264Opts,
			stdin = poVideo1.stdout,
			stdout = subprocess.PIPE,
			stderr = subprocess.PIPE,#
			shell = False)

		return poVideo

	def getProgress(self):
		while True:
			try:
				line = self.queue.get_nowait()
				match = re.search('(\d+) *\/ *(\d+) *frames', line);
				if match != None:
					self.progress = int( match.group(1) )
			except queue.Empty:
				break
		return (self.progress, self.totalFrameCount)


class AudioEncodeExecutor(EncodeExecutor):
	def __init__(self, infile, outfile, mi, ffmpegCommonOpts):
		EncodeExecutor.__init__(self, infile, outfile, mi, ffmpegCommonOpts)
		self.frameCount = 0

	def startProcess(self):
		mi = self.mi["Audio"]
		
		ffmpegAudioOpts = ['-vn', '-f', 'wav', '-']
		faacOpts = ['--no-midside']
		
		# Sampling rate
		if 'SamplingRate' in mi and '' != mi['SamplingRate']:
			samplingRate = int(mi['SamplingRate'])
			samplingRate = min(441000, samplingRate)
			faacOpts += ['-c', str(samplingRate)]

		# -q and -a are equvalent. e.g. -q 100 (at 44.1khz) and -a 64 result in exactly the same output.
		if True:
			faacOpts += ['-q', str(100)] # quantizer qualifier (def:100) 100=approx.128kbps in 2ch 16bit 44.1khz
		else:
			faacOpts += ['-b', str(64)] # average bitrate per channel

		faacOpts += ['-o', self.outfile, '-']
		
		poAudio1 = subprocess.Popen(
			['ffmpeg'] + self.ffmpegCommonOpts + ffmpegAudioOpts,
			stdout = subprocess.PIPE,
			stderr = subprocess.PIPE,
			shell = False)
		poAudio  = subprocess.Popen(
			['faac'] + faacOpts,
			stdin = poAudio1.stdout,
			stdout = subprocess.PIPE,
			stderr = subprocess.PIPE,#
			shell = False)
		return poAudio

	def getProgress(self):
		while True:
			try:
				line = self.queue.get_nowait()
				match = re.search('(\d+) *\| +(\d+\.\d+) *\| *(\d+\.\d+)x', line);
				if match != None:
					self.frameCount = int( match.group(1) )
			except queue.Empty:
				break
		return (self.frameCount, None)
	

class VideoEncoder:
	def __init__(self):
		self.mi = None
		self.retcode = 1
		
		self.stdscr = None
		self.argsParser = None

	def __del__(self):
		self.close()
		
	def getArgumentParser(self):
		if self.argsParser: return self.argsParser
		parser = argparse.ArgumentParser(conflict_handler='resolve')
		parser.add_argument('--infile', '-i', dest='infile', required = True)
		parser.add_argument('--outfile', '-o', required = True)
		parser.add_argument('--start', type=float, default=0)
		parser.add_argument('--verbose', action='store_const', const=True)
		parser.add_argument('--force', dest='forceOverwrite', action='store_const', const=True)
		parser.add_argument('--duration', type=float, default=float('inf'))
		parser.add_argument('--noaudio', dest='noAudio', action='store_const', const=True)
		parser.add_argument('--progress', action='store_const', const=True)
		self.argsParser = parser
		return self.argsParser

	def initCurses(self):
		self.logVerbose("Initializing curses.")
		self.stdscr = curses.initscr()
		curses.noecho() # Don't echo what user inputs.
		curses.cbreak() # Enable cbreak mode: respond instantly to what user inputs.
		self.stdscr.keypad(1) # Don't know well...
		self.logVerbose("Curses is initialized.")
	
	def closeCurses(self):
		if self.stdscr:
			curses.nocbreak()
			self.stdscr.keypad(0)
			curses.echo()
			curses.endwin()
			self.stdscr = None
	
	def close(self):
		self.closeCurses()
	
	def getFfmpegCommonOpts(self):
		opts = ['-i', self.args.infile, '-v', '0', '-ss', str(self.args.start)]
		if self.args.duration < float('inf'):
			opts += ['-t', str(self.args.duration)]
		return opts
	
	def outputProgress(self, prefix, ypos, progress, progressTotal):
		if self.stdscr == None: return None
		(h, w) = self.stdscr.getmaxyx()
		w -= 1
		str = prefix

		if progress != None:
			if progressTotal != None:
				ratio = float(progress) / progressTotal
				if ratio < 0: ratio = 0
				if ratio > 1: ratio = 1
				str += '%6d/%6d ' % (progress, progressTotal)
				wprog = w - len(str) - 5
				prog = int(ratio * wprog)
				str += ('#' * prog) + ' -+*'[int( 4 * (ratio * wprog - prog) )] + (' ' * (wprog-prog-1)) + '|'
			else:
				str += '%6d' % progress
		else:
			str += 'Done'
				
		
		if len(str) > w:
			str = str[0:w]
		self.stdscr.move(h-ypos, 0)
		self.stdscr.clrtoeol()
		self.stdscr.addstr(str)
		self.stdscr.refresh()
	
	
	def getMediaInfo(self, file):
		mi = mediainfo.MediaInfo(file)
		try:
			tags = {
				"General" :
				[
					"Format",
					"Format_Profile",
					"VideoCount",
					"AudioCount",
					"FileSize",
					"Duration",
					"SamplingRate",
				],
			
				"Video":
				[
					"Format",
					"Format_Profile",
					"Codec",
					"FrameCount",
					"Width",
					"Height",	
					"Duration",
					"BitRate_Mode",
					"Bits-(Pixel*Frame)",
					"FrameRate",
					"StreamSize",
					"DisplayAspectRatio"
				],
			
				"Audio":
				[
					"Format",
					"Format_Profile",
					"Codec",
					"BitRate",
					"BitRate_Mode",
					"Channels",
					"SamplingRate",
					"Resolution",
					"SamplingCount",
					"Duration",
					"StreamSize",
				],
			}
			
			result = { }
			for cls in tags.keys():
				result[cls] = mi.querySingleClass(cls, tags[cls])
			
			return result
		finally:
			mi.close()
		
	def convertToHumanReadable(self, val, units, chunks, format=None):
		if len(units) != len(chunks) + 1:
			raise Exception("The number of chunks must be one less than that of units.")
		val = float(val)
		for i in range(0, len(chunks)):
			if val < chunks[i]:
				tup = (val, units[i])
				return tup if format == None else format % tup
			val /= chunks[i]
		
		tup = (val, units[-1])
		return tup if format == None else format % tup
		
	def bytesToHumanReadable(self, bytes, units=["B", "KiB", "MiB", "GiB", "TiB"], format=None):
		return self.convertToHumanReadable(bytes, units, [1024, 1024, 1024, 1024], format)
	
	def secondsToHumanReadable(self, seconds, units=["s", "m", "h", "d"], format=None):
		return self.convertToHumanReadable(seconds, units, [60, 60, 24], format)

	def logVerbose(self, s):
		if self.args.verbose:
			if isinstance(s, unicode): s = s.encode('utf-8')
			sys.stdout.write(s + "\n")
	
	def run(self, args):
		self.args = args
		tmp = None
		self.retcode = 1

		try:
			# Check for validity of command-line options.
			
			infile  = self.args.infile
			outfile = self.args.outfile
			
			if not os.path.isfile(infile): raise VideoEncoderError('Input file is not a normal file: %s' % infile)
			if os.path.isdir(outfile): raise VideoEncoderError('Output file is a directory: %s' % outfile)
			if os.path.isfile(outfile):
				if not self.args.forceOverwrite:
					ans = input('Output file already exists. Overwrite? [yN] ')
					if ans != 'y' and ans != 'Y':
						raise CancelByUserError
			
			# Temporary directory.
			
			tmp = tempfile.mkdtemp(prefix = 'VideoEncoder_')
			logfile = open(os.path.join(tmp, 'log'), 'w')
			logfile.write("infile: %s\n" % infile.encode('utf-8'))
			
			# Retrieve media information.
			
			self.logVerbose("Retrieving media information...")
			self.mi = self.getMediaInfo(infile)
			with open(os.path.join(tmp, 'mediainfo'), 'w') as fp:
				for sec, m in self.mi.iteritems():
					for tag, v in m.iteritems():
						fp.write("%s.%s : \"%s\"\n" % (sec, tag, v.encode('utf-8')))
						sys.stdout.write("%s.%s : \"%s\"\n" % (sec, tag, v.encode('utf-8')))						
			
			videoCount = self.mi["General"]["VideoCount"]
			audioCount = self.mi["General"]["AudioCount"]
			videoCount = 0 if videoCount == "" else int(videoCount)
			audioCount = 0 if audioCount == "" else int(audioCount)

			self.logVerbose("VideoCount: %d" % videoCount)
			self.logVerbose("AudioCount: %d" % audioCount)
			
			if videoCount != 1:
				raise MediaFileNotSupportedError("Media file with video stream count other than 1 is not supported.")
			if audioCount > 1:
				raise MediaFileNotSupportedError("Media file with two or more audio streams is not supported.")
			
			# Initialize curses.

			if self.args.progress:
				self.initCurses()
			
			# Prepare for encoding.
			
			mp4TempOut = os.path.join(tmp, 'out.mp4')

			videoEnable = (videoCount == 1)
			audioEnable = (audioCount == 1) and not self.args.noAudio
			
			# Begin encoding.
			

			self.logVerbose('Begin encoding.')
			videoExec = None
			audioExec = None

			if videoEnable:
				videoTempOut = os.path.join(tmp, 'video.264')
				videoExec = VideoEncodeExecutor(infile, videoTempOut, self.mi, self.getFfmpegCommonOpts())
				videoExec.start()
			
			if audioEnable:
				audioTempOut = os.path.join(tmp, 'audio.aac')
				audioExec = AudioEncodeExecutor(infile, audioTempOut, self.mi, self.getFfmpegCommonOpts())
				audioExec.start()
			
			# Loop until encode finishes.
			
			videoFrame = 0
			time0 = time.time()

			#--------------------
			# Decode video/audio
			#--------------------

			progressRatio = 0
			
			while True:
				# Note:
				#  Popen.poll() checks if the process is terminated, and if so, set and return the return code.
				#  Return code is None if the process is running, negative if the process is terminated by 
				#  signal abs(return code).
				
				elapsedSeconds = time.time() - time0
				if progressRatio > 0:
					remSeconds = elapsedSeconds * (1-progressRatio) / progressRatio
				else:
					remSeconds = 0
				if self.stdscr != None:
					(h, w) = self.stdscr.getmaxyx()
					self.stdscr.move(h-1, 0)
					self.stdscr.clrtoeol()
					self.stdscr.addstr('Elap: %.1f %s  Rem: %.1f %s' % (self.secondsToHumanReadable(elapsedSeconds) + self.secondsToHumanReadable(remSeconds)))
					self.stdscr.refresh()
				else:
					sys.stdout.write('Elap: %.1f %s  Rem: %.1f %s' % (self.secondsToHumanReadable(elapsedSeconds) + self.secondsToHumanReadable(remSeconds)) + "\n")
				
				# video
				if videoExec != None:
					ret = videoExec.getReturnCode()
					if ret == None:
						(progress, progressTotal) = videoExec.getProgress()
						self.outputProgress('V: ', 1, progress, progressTotal)
						if progressTotal != None:
							progressRatio = float(progress) / progressTotal
						else:
							progressRatio = 0
					else:
						# video finishes
						if self.stdscr == None:
							self.logVerbose('Video encoding done.')
						if ret != 0:
							raise SubprocessFailedError('Video encoder failed with return code %d.' % ret)
						videoExec = None
						
				
				# audio
				if audioExec != None:
					ret = audioExec.getReturnCode()
					if ret == None:
						(progress, progressTotal) = audioExec.getProgress()
						self.outputProgress('A: ', 2, progress, progressTotal)
					else:
						# audio finishes
						if self.stdscr == None:
							self.logVerbose('Audio encoding done.')
						self.outputProgress('A: ', 2, None, None)
						if ret != 0:
							raise SubprocessFailedError('Audio encoder faled with return code %d.' % ret)
						audioExec = None
				
				# If both video and audio finish, exit the loop.
				if audioExec == None and videoExec == None:
					break
				
				time.sleep(0.5)
			
			self.closeCurses()

			#----------------
			# MP4 mux
			#----------------

			if videoEnable:
				trackId = 1
				videoWidth  = int(self.mi['Video']['Width'])
				videoHeight = int(self.mi['Video']['Height'])
				opts = [ ]
				opts += ['-new']
				opts += ['-add', videoTempOut]
				opts += ['-fps', self.mi["Video"]["FrameRate"]]

				try:
					dar = self.mi['Video']['DisplayAspectRatio']
					numDen = self.aspectRatioFloatToTuple(dar)
					if numDen != None:
						dar = '%d:%d' % (numDen[0] * videoHeight, numDen[1] * videoWidth)
						opts += [ '-par', '%d=%s' % (trackId,dar) ]
				except ValueError:
					pass

				ret = self.execMP4Box(opts, mp4TempOut, mp4TempOut)
				if ret != 0:
					raise SubprocessFailedError("Video muxing failed with return code %d." % ret)
				videoExec = None


			if audioEnable:
				opts = ['-add', audioTempOut]
				ret = self.execMP4Box(opts, mp4TempOut, mp4TempOut)
				if ret != 0:
					raise SubprocessFailedError("Audio muxing failed with return code %d." % ret)
				audioExec = None

			sys.stdout.write('MP4 muxing is done.' + "\n")

			#-------------------
			# MP4 optimization
			#-------------------
			# Note: Without changing working directory, this will fail.
			
			prevcwd = os.getcwd()
			try:
				self.logVerbose("cd'ing '%s'\n" % tmp)
				os.chdir(tmp)
				
				ret = self.execMP4Box(['-hint'], mp4TempOut, mp4TempOut)
				if ret != 0:
					raise SubprocessFailedError("MP4Box failed with return code %d." % ret)

			finally:
				self.logVerbose("cd'ing '%s'\n" % prevcwd)
				os.chdir(prevcwd)

			# Move resulted file.
			
			#shutil.move(mp4TempOut, outfile)
			self.logVerbose("Moving...")
			shutil.move(mp4TempOut, outfile)
			
			# Show new media information.
			
			mi = self.getMediaInfo(outfile)
			
			if True:
				#if self.mi["General"]["Duration"] != mi["General"]["Duration"]:
				#	print("Warning: Overall duration changed : %s -> %s." % (self.mi["General"]["Duration"], mi["General"]["Duration"]))
				pass
			if videoEnable:
				if self.mi["Video"]["Width"] != mi["Video"]["Width"]:
					print("Warning: Video width changed : %s -> %s." % (self.mi["Video"]["Width"], mi["Video"]["Width"]))
				if self.mi["Video"]["Height"] != mi["Video"]["Height"]:
					print("Warning: Video height changed : %s -> %s." % (self.mi["Video"]["Height"], mi["Video"]["Height"]))
				#if self.mi["Video"]["Duration"] != mi["Video"]["Duration"]:
				#	print("Warning: Video duration changed : %s -> %s." % (self.mi["Video"]["Duration"], mi["Video"]["Duration"]))
				#if self.mi["Video"]["FrameCount"] != mi["Video"]["FrameCount"]:
				#	print("Warning: Video frame count changed : %s -> %s." % (self.mi["Video"]["FrameCount"], mi["Video"]["FrameCount"]))
				if self.mi["Video"]["FrameRate"] != mi["Video"]["FrameRate"]:
					print("Warning: Video frame rate changed : %s -> %s." % (self.mi["Video"]["FrameRate"], mi["Video"]["FrameRate"]))
				pass
			if audioEnable:
				if self.mi["Audio"]["Channels"] != mi["Audio"]["Channels"]:
					print("Warning: Audio channel count changed : %s -> %s." % (self.mi["Audio"]["Channels"], mi["Audio"]["Channels"]))
				#if self.mi["Audio"]["Duration"] != mi["Audio"]["Duration"]:
				#	print("Warning: Audio duration changed : %s -> %s." % (self.mi["Audio"]["Duration"], mi["Audio"]["Duration"]))
				#if self.mi["Audio"]["SamplingCount"] != mi["Audio"]["SamplingCount"]:
				#	print("Warning: Audio sampling count changed : %s -> %s." % (self.mi["Audio"]["SamplingCount"], mi["Audio"]["SamplingCount"]))
				pass
			
			if True:
				print("G:%6.1f ->%6.1f MiB" % (
					float(self.mi["General"]["FileSize"]) / 1024 / 1024,
					float(     mi["General"]["FileSize"]) / 1024 / 1024,
				))

			self.retcode = 0
		except KeyboardInterrupt as e:
			raise
		except InsufficientOptionParametersError as e:
			print("Option %s requires more parameters." % e)
		except InvalidOptionError as e:
			print("Unknown option: %s" % e)
		except MediaFileNotSupportedError as e:
			print(e)
		except InsufficientOptionsError as e:
			print(e)
		except VideoEncoderError as e:
			print(e)
		except CancelByUserError as e:
			pass
		finally:
			if tmp != None:
				try:
					shutil.rmtree(tmp)
				except:
					pass
				pass
		return self.retcode

	def execMP4Box(self, opts, inPath, outPath):
		# Note:
		# MP4Box will fail if the output file and the temporary file (which MP4Box creates) lie in different partition.
		
		tmpOut = tempfile.NamedTemporaryFile(suffix = '.mp4')
		
		cmd = ['MP4Box', inPath]
		cmd += opts
		cmd += [ '-out', tmpOut.name ]
		ret = subprocess.call(cmd)
		if ret != 0:
			return ret
		shutil.copyfile(tmpOut.name, outPath)
		return 0

	def aspectRatioFloatToTuple(self, ar):
		assert(isinstance(ar, str) or isinstance(ar, unicode))
		idot = ar.find('.')
		numDigitsBelowDot = len(ar) - idot - 1
		fmt = '%%.%df' % numDigitsBelowDot
		
		for num in xrange(1,10):
			for den in xrange(1,10):
				ar2 = fmt % (float(num) / den)
				if ar == ar2:
					return (num, den)
		return None
