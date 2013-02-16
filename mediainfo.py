# -*- mode:python; indent-tabs-mode:nil; python-indent:4 -*-
import subprocess
import signal

class MediaInfoException(Exception): pass
class MediaFileNotSupportedError(MediaInfoException): pass
class MediaInfoInvalidResultError(MediaInfoException): pass

def subprocessPreexec():
    signal.signal(signal.SIGINT, signal.SIG_IGN)

class MediaInfo:
    def __init__(self, mediaFile):
        self.mediaFile = mediaFile
	
    def close(self):
        pass
	
    def querySingle(self, tag):
        cmd = ["mediainfo", "--Inform=%s" % tag, self.mediaFile]
        popen = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            shell=False, preexec_fn = subprocessPreexec)
        val = popen.communicate()[0].split(b"\n")[0].decode("utf8")
        if popen.returncode != 0:
            raise MediaFileNotSupportedError("mediainfo failed with code %d." % popen.returncode)
        return val
	
    def query(self, tags):
        d = { }
        for tag in tags:
            d[tag] = self.querySingle(tag)
        return d
	
    def querySingleClass(self, cls, tags):
        return self.querySingleSection(cls, tags)
        
    def querySingleSection(self, section, tags):
        d = { }
        informStr = section + ';'
        for tag in tags:
            informStr += '%' + tag + "%\n"
        
        cmd = ['mediainfo', '--Inform=%s' % informStr, self.mediaFile]
        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=False, preexec_fn = subprocessPreexec)
        data = popen.communicate()[0]

        if popen.returncode != 0:
            raise MediaFileNotSupportedError('mediainfo failed with code %d.' % popen.returncode)

        d = { }
        lines = data.decode('utf-8').split("\n")
        #if len(tags) > len(lines):
        #    raise MediaInfoInvalidResultError()
        
        for i in xrange(len(tags)):
            if i < len(lines):
                d[tags[i]] = lines[i]
            else:
                d[tags[i]] = ''
        return d
    
    def queryFull(self):
        cmd = ['mediainfo', '--Full', self.mediaFile]
        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=False, preexec_fn = subprocessPreexec)
        section = None
        result = { }
        for line in popen.stdout:
            if len(line) == 0: break
            line = line.decode('utf-8').rstrip()
            if len(line) == 0: continue
            fields = line.split(':', 1)
            if len(fields) == 1:
                section = fields[0]
                result[section] = { }
                continue
            if section == None: raise MediaInfoInvalidResultError()
            tag   = fields[0].rstrip()
            value = fields[1].lstrip()
            result[section].setdefault(tag, []).append(value)
        return result

    def queryMultiSections(self, spec):
        d = { }
        for section, tags in spec.items():
            d[section] = self.querySingleSection(section, tags)
        return d
