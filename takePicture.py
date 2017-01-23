

import subprocess as sp
import tempfile
import sys
# from PyQt5.QtWidgets import *
# from PyQt5.QtGui import *
# from PyQt5.QtCore import Qt, QTimer, pyqtSlot
import numpy
# from scipy import ndimage
from scipy.misc import imsave
import usb.core
import usb.util
from datetime import datetime
import threading
from Queue import Queue
import time

lastCam=None
lastTerm=None

# app = QApplication(sys.argv)

calImage=None

# COLORMAP = []
# for i in range(255):
#     COLORMAP.append(qRgb(i, i, i))
cnt=0

def termWorker():
	global calImage, lastTerm
	dev = usbinit()
	camerainit(dev)
	calImage = get_cal_image(dev)
	for a in range(5):
		image = get_image(dev)
		imsave ('termImage'+)str(a)+'.png',image)

		# bytesPerLine = 208
		# qImg = QImage(image, 208, 156, bytesPerLine, QImage.Format_Indexed8)
		# qImg.setColorTable(COLORMAP)
		# qImg.save('image'+str(a)+'.png')

def usbinit():
	# find our Seek Thermal device  289d:0010
	dev = usb.core.find(idVendor=0x289d, idProduct=0x0010)

	# was it found?
	if dev is None:
    	    raise ValueError('Device not found')

	# set the active configuration. With no arguments, the first
	# configuration will be the active one
	dev.set_configuration()

	# get an endpoint instance
	cfg = dev.get_active_configuration()
	intf = cfg[(0,0)]

	ep = usb.util.find_descriptor(
	    intf,
    # match the first OUT endpoint
    	    custom_match = \
    	    lambda e: \
		usb.util.endpoint_direction(e.bEndpointAddress) == \
    		usb.util.ENDPOINT_OUT)

	assert ep is not None

	return dev

# send_msg sends a message that does not need or get an answer
def send_msg(dev,bmRequestType, bRequest, wValue=0, wIndex=0, data_or_wLength=None, timeout=None):
	assert (dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, data_or_wLength, timeout) == len(data_or_wLength))

# alias method to make code easier to read
# receive msg actually sends a message as well.
def receive_msg(dev,bmRequestType, bRequest, wValue=0, wIndex=0, data_or_wLength=None, timeout=None):
	zz = dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, data_or_wLength, timeout) # == len(data_or_wLength))
	return zz

# De-init the device
def deinit(dev):
	msg = '\x00\x00'
        for i in range(3):
	    send_msg(dev,0x41, 0x3C, 0, 0, msg)           # 0x3c = 60  Set Operation Mode 0x0000 (Sleep)

# Camera initilization
def camerainit(dev):

	try:
	    msg = '\x01'
	    send_msg(dev,0x41, 0x54, 0, 0, msg)              # 0x54 = 84 Target Platform 0x01 = Android
	except Exception as e:
	    deinit(dev)
	    msg = '\x01'
	    send_msg(dev,0x41, 0x54, 0, 0, msg)              # 0x54 = 84 Target Platform 0x01 = Android

	send_msg(dev,0x41, 0x3C, 0, 0, '\x00\x00')              # 0x3c = 60 Set operation mode    0x0000  (Sleep)
	ret1 = receive_msg(dev,0xC1, 0x4E, 0, 0, 4)             # 0x4E = 78 Get Firmware Info

	ret2 = receive_msg(dev,0xC1, 0x36, 0, 0, 12)            # 0x36 = 54 Read Chip ID

	send_msg(dev,0x41, 0x56, 0, 0, '\x20\x00\x30\x00\x00\x00')                  # 0x56 = 86 Set Factory Settings Features
	ret3 = receive_msg(dev,0xC1, 0x58, 0, 0, 0x40)                              # 0x58 = 88 Get Factory Settings

	send_msg(dev,0x41, 0x56, 0, 0, '\x20\x00\x50\x00\x00\x00')                  # 0x56 = 86 Set Factory Settings Features
	ret4 = receive_msg(dev,0xC1, 0x58, 0, 0, 0x40)                              # 0x58 = 88 Get Factory Settings

	send_msg(dev,0x41, 0x56, 0, 0, '\x0C\x00\x70\x00\x00\x00')                  # 0x56 = 86 Set Factory Settings Features
	ret5 = receive_msg(dev,0xC1, 0x58, 0, 0, 0x18)                              # 0x58 = 88 Get Factory Settings

	send_msg(dev,0x41, 0x56, 0, 0, '\x06\x00\x08\x00\x00\x00')                  # 0x56 = 86 Set Factory Settings Features   
	ret6 = receive_msg(dev,0xC1, 0x58, 0, 0, 0x0C)                              # 0x58 = 88 Get Factory Settings

	send_msg(dev,0x41, 0x3E, 0, 0, '\x08\x00')                                  # 0x3E = 62 Set Image Processing Mode 0x0008
	ret7 = receive_msg(dev,0xC1, 0x3D, 0, 0, 2)                                 # 0x3D = 61 Get Operation Mode

	send_msg(dev,0x41, 0x3E, 0, 0, '\x08\x00')                                  # 0x3E = 62 Set Image Processing Mode  0x0008
	send_msg(dev,0x41, 0x3C, 0, 0, '\x01\x00')                                  # 0x3c = 60 Set Operation Mode         0x0001  (Run)
	ret8 = receive_msg(dev,0xC1, 0x3D, 0, 0, 2)                                 # 0x3D = 61 Get Operation Mode

def read_frame(dev): # Send a read frame request

	send_msg(dev,0x41, 0x53, 0, 0, '\xC0\x7E\x00\x00')                 # 0x53 = 83 Set Start Get Image Transfer

	try:
		data  = dev.read(0x81, 0x3F60, 1000)
		data += dev.read(0x81, 0x3F60, 1000)
		data += dev.read(0x81, 0x3F60, 1000)
		data += dev.read(0x81, 0x3F60, 1000)
	except usb.USBError as e:
		sys.exit()
	return data

def add_207(imgF):  
	# Add (really subtract) the data from the 207 row to each pixil
	# or not depending on the testing some of the following may be commented out.
	# there are a different # of black dots in each row so the divisor
	# needs to change for each row according to what is in the dot_numbers.txt file.
	# this may not be the best way to do this. The code below does not do this now.
	# need to try to use numpy or scipy to do this as it is a real hit on cpu useage.
	# But doing it only for the cal image doesn't impact the real time images.
	tuning = 200 / 150.0

	z = (.002 * imgF[:,206].mean())
	z1 = z * tuning

	for i in range(0,156,1):
	    for j in range(0,205,1):
		    imgF[i,j] = imgF[i,j] - (.05 * imgF[i,j]/z) - imgF[i,206]/z1 # try scaled pixil and scaled pixil 207
	return


def get_cal_image(dev):
	# Get the first cal image so calImage isn't null
	status = 0

	#  Wait for the cal frame
	ret9=None
	while status != 1:
		# Read a raw frame
		ret9 = read_frame(dev)
		status = ret9[20]

	return processCallImage(ret9)

def processCallImage(frame):
	print 'calibration frame'
	#  Convert the raw 16 bit calibration data to a PIL Image
	calimgI = numpy.fromstring(frame, 'uint16',208*156).reshape((156,208))
	# calimgI = numpy.asarray(frame)
	# print calimgI.shape
	# calimgI = calimgI.reshape((208,156))

	#  Convert the PIL Image to an unsigned numpy float array
	im2arr = numpy.asarray(calimgI)

	# clamp values < 2000 to 2000
	im2arr = numpy.where(im2arr < 2000, 2000, im2arr)
	im2arrF = im2arr.astype('float')

	# Clamp pixel 40 to 2000 so it doesn't cause havoc as it rises to 65535
	im2arrF[0,40] = 2000

	# Add the row 207 correction (maybe) >>Looks like it needs to be applied to just the cal frame<<
	add_207(im2arrF)

	# Zero out column 207
	im2arrF[:,206] = numpy.zeros(156)

	return im2arrF

def get_image(dev):

	global calImage
	status = 0

	#  Wait for the next image frame, ID = 3 is a Normal frame
	while status != 3:
		# Read a raw frame
		ret9 = read_frame(dev)
		status = ret9[20]

		# check for a new cal frame, if so update the cal image
		# if status == 1:
	 #   		calImage = processCallImage(ret9)
	return giMine(ret9)	 


def giMine(ret9):
	global calImage
	#  If this is normal image data
	#  Convert the raw 16 bit thermal data to a PIL Image
	imgx = numpy.fromstring(ret9, 'uint16',208*156).reshape((156,208))

	#  Convert the PIL Image to an unsigned numpy float array
	im1arr = numpy.asarray(imgx)

	# clamp values < 2000 to 2000
	im1arr = numpy.where(im1arr < 2000, 2000, im1arr)
	im1arrF = im1arr.astype('float')

	# Clamp pixel 40 to 2000 so it doesn't cause havoc as it rises to 65535
	im1arrF[0,40]  = 2000

	# Zero out column 207
	im1arrF[:,206] = numpy.zeros(156)

	#  Subtract the most recent calibration image from the offset image data
	#  With both the cal and image as floats, the offset doesn't matter and
	#  the following image conversion scales the result to display properly
	additionF = (im1arrF) + 884 - (calImage)

	# tempCenter = additionF[80][100]*36/1000
	# print 'center temperature\t'+str(tempCenter)

	#  Try removing noise from the image, this works suprisingly well, but takes some cpu time
	#  It gets rid of bad pixels as well as the "Patent Pixils"
	############# DO NOT DO THIS #########
	noiselessF = additionF #ndimage.median_filter(additionF, 3)

	bottom = 0
	top = 100

	display_min = bottom * 4
	display_max = top * 16
	image8 = noiselessF

	image8.clip(display_min, display_max, out=image8)
	image8 -= display_min
	image8 //= (display_max - display_min + 1) / 256.
	image8 = image8.astype(numpy.uint8)

	noiselessI8= image8

	# conv = colorscale.GrayToRGB(colorscale.IronPalette())
	# cred = numpy.frompyfunc(conv.get_red, 1, 1)
	# cgreen = numpy.frompyfunc(conv.get_green, 1, 1)
	# cblue = numpy.frompyfunc(conv.get_blue, 1, 1)

	# # Convert to a PIL image sized to 640 x 480
	# color = numpy.dstack((cred(noiselessI8).astype(noiselessI8.dtype), cgreen(noiselessI8).astype(noiselessI8.dtype), cblue(noiselessI8).astype(noiselessI8.dtype)))
	# imgCC = Image.fromarray(color).resize((640, 480),Image.ANTIALIAS).transpose(3)
	# imgCC.save('CImage'+str(cnt)+'.png')
	return noiselessI8


tTERM = threading.Thread(target=termWorker)
tTERM.start()
tTERM.join()
