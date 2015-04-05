# -*- mode:python; indent-tabs-mode:t; python-indent:4 -*-

import os
import sys

# for backward compatibility
from nib import (
	encodePath,
	progress
	)

def makeRelativePath(targetPath, sourcePath):
	#print(targetPath, sourcePath)
	if targetPath == sourcePath:
		return ''
	isabs1 = os.path.isabs(targetPath)
	isabs2 = os.path.isabs(sourcePath)
	assert isabs1 == isabs2

	if isabs1:
		drv1, targetPath = os.path.splitdrive(targetPath)
		drv2, sourcePath = os.path.splitdrive(sourcePath)
		assert drv1 == drv2

	sep = os.sep
	if isinstance(targetPath, bytes):
		sep = sep.encode('utf-8')

	parts1 = targetPath.split(sep)
	parts2 = sourcePath.split(sep)
	while len(parts1) > 0 and len(parts2) > 0 and parts1[0] == parts2[0]:
		parts1.pop(0)
		parts2.pop(0)

	if parts2 == ['']:
		parts2 = []
	parts1 = ['..'] * len(parts2) + parts1
	return os.path.join(*parts1)

def md5(path, file=True):
	import hashlib
	m = hashlib.md5()

	if file:
		f = open(encodePath(path), 'rb')
		while True:
			data = f.read(8192)
			if not data: break
			m.update(data)
		f.close()
	else:
		m.update(path)

	return m.hexdigest()

