# -*- coding: utf-8 -*- 

"""
Define camera driver classes for FLIR cameras
"""

import numpy as np
from CameraClassDef import CameraClass

# PySpin driver for FLIR cameras
try : 
    import PySpin 
    PySpinDriverInstalled = True
except :
    print('ERROR ! : Tried to load PySpin driver, but it is not installed')
    PySpinDriverInstalled = False


class FLIRPySpinClass(CameraClass) :
    """Parent class for FLIR cameras using PySpin python driver.
    
    Used as generic driver class if no model-specific child class is defined in same file below"""
    
    def __init__(self, cameraNumber, triggerMode=0, exposurems=1, 
                 gaindB=1, camROI=None, loadDefault = False) :	
        """Initialize the Camera object 
        
        Args:
            cameraNumber (int) : index of camera in camerasConfigs list
            
        Keyword Args:
            triggerMode=0  (int) : 0 for hardware/external, 1 for software/internal
            
            exposurems=1. (float) : Exposition duration (exposure) in ms.
            
            gaindB=0. (float) : hardware gain of the camera in dB.
            
            camROI=None (None or [int]*4) : Camera region of interest to read from sensor
                [x offset , y offset , x size , y size ] (binning is not implemented)
            
            loadDefault = True  (bool): Decide if default values from cameraConfigs should be set at creation 
                        
        Return: 
            FLIRPySpinClass camera object
        """
        # Inicializa variáveis internas nulas para ignorar as travas de escrita da classe base
        self._exposurems = float(exposurems)
        self._gaindB = float(gaindB)
        self._camROI = camROI
        
        super().__init__(cameraNumber, triggerMode=triggerMode, exposurems=exposurems,
                         gaindB=gaindB, camROI=camROI, loadDefault=loadDefault)
        
        self.cameraDriverInstalled = PySpinDriverInstalled
        if not(self.cameraDriverInstalled) :
             return None
             
        # find camera in connected system list
        self.pySpinSystem = PySpin.System.GetInstance()
        self.pySpinCameraList = self.pySpinSystem.GetCameras()
        
        for icam in range(self.pySpinCameraList.GetSize()) :
            cam = self.pySpinCameraList.GetByIndex(icam)
            # detect if serial number match config
            if str(self.cameraConfig['serial']) in cam.GetUniqueID() :
                self.pySpinCamera = cam
                self.cameraConnected = True
                break
        
        if not(self.cameraConnected) :
            print('ERROR ! : Could not connect camera '+str(self._cameraNumber) +' (maybe check serial number)')
            return None
            
        #connect camera
        self.pySpinCamera.Init()
        
        # --- PROTEÇÃO GIGE CONTRA NÓS TRAVADOS ---
        self.imageBitDepth = int(self.cameraConfig['imageBitDepth']) 
        try:
            if self.imageBitDepth <= 8 :
                self.pySpinCamera.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
            else :
                self.pySpinCamera.PixelFormat.SetValue(PySpin.PixelFormat_Mono16)
        except PySpin.SpinnakerException as e:
            print(f"[Aviso] O nó PixelFormat estava travado pelo hardware, ignorado de forma segura.")
        # ----------------------------------------

        # get maximum intensity value of sensor read
        self.maxLevel = 2**self.imageBitDepth - 1
        
        # load default if asked
        if loadDefault : 
            self.setTriggerMode(self.triggerMode)
            self.setExposurems(float(self.cameraConfig['defaultExposurems']))
            self.setGaindB(float(self.cameraConfig['defaultGaindB']))
            if not(self.cameraConfig['defaultCamROI'] is None) :
                self.setCamROI(self.cameraConfig['defaultCamROI'])
        else :
            self.setTriggerMode(self.triggerMode)
            self.setExposurems(exposurems)
            self.setGaindB(gaindB)
            if not(camROI is None) :
                self.setCamROI(camROI)
                
        # create spin image processor for grab operation
        self.pySpinImageProcessor = PySpin.ImageProcessor()
        self.pySpinImageProcessor.SetColorProcessing(PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR)
        
        # start camera acquisition loop 
        self.startAcquisition()
        
    def __del__(self) : 
        self.close()

    def close(self) :
        if self.cameraConnected :
            self.stopAcquisition()
            self.pySpinCamera.DeInit()
            del self.pySpinCamera
            self.cameraConnected = False
            self.pySpinCameraList.Clear()
            self.pySpinSystem.ReleaseInstance()
            
    def startAcquisition(self) :
        if self.cameraConnected and not(self.pySpinCamera.IsStreaming()) :
            self.pySpinCamera.BeginAcquisition()
            
    def stopAcquisition(self) :
        if self.cameraConnected and self.pySpinCamera.IsStreaming() :
            self.pySpinCamera.EndAcquisition()

    def setTriggerMode(self, triggerMode) :
        self._triggerMode = triggerMode
        if triggerMode == 0 :
            self.pySpinCamera.TriggerMode.SetValue(PySpin.TriggerMode_Off)
            self.pySpinCamera.TriggerSource.SetValue(PySpin.TriggerSource_Line0)
            self.pySpinCamera.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)
            self.pySpinCamera.TriggerMode.SetValue(PySpin.TriggerMode_On)
        elif triggerMode == 1 :
            self.pySpinCamera.TriggerMode.SetValue(PySpin.TriggerMode_Off)
            self.pySpinCamera.TriggerSource.SetValue(PySpin.TriggerSource_Software)
            self.pySpinCamera.TriggerMode.SetValue(PySpin.TriggerMode_On)
            
    def setExposurems(self, exposurems) :
        if hasattr(self, 'pySpinCamera'):
            self.pySpinCamera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
            self.pySpinCamera.ExposureMode.SetValue(PySpin.ExposureMode_Timed)
            self.pySpinCamera.ExposureTime.SetValue(float(exposurems)*1000.)
            self._exposurems = self.pySpinCamera.ExposureTime.GetValue()/1000.
        else:
            self._exposurems = float(exposurems)
        
    @property
    def exposurems(self) :
        if self.cameraConnected and hasattr(self, 'pySpinCamera'):
            self._exposurems = self.pySpinCamera.ExposureTime.GetValue()/1000.
        return self._exposurems

    @exposurems.setter
    def exposurems(self, val):
        self.setExposurems(val)

    def setGaindB(self, gaindB) :
        if hasattr(self, 'pySpinCamera'):
            self.pySpinCamera.GainAuto.SetValue(PySpin.GainAuto_Off)
            self.pySpinCamera.Gain.SetValue(float(gaindB))
            self._gaindB = self.pySpinCamera.Gain.GetValue()
        else:
            self._gaindB = float(gaindB)
        
    @property
    def gaindB(self) :
        if self.cameraConnected and hasattr(self, 'pySpinCamera'):
            self._gaindB = self.pySpinCamera.Gain.GetValue()
        return self._gaindB

    @gaindB.setter
    def gaindB(self, val):
        self.setGaindB(val)

    def setCamROI(self, camROI) :
        if not hasattr(self, 'pySpinCamera'):
            self._camROI = camROI
            return
            
        if camROI is None :
            self.pySpinCamera.Width.SetValue(self.pySpinCamera.Width.GetMax())
            self.pySpinCamera.Height.SetValue(self.pySpinCamera.Height.GetMax())
            self.pySpinCamera.OffsetX.SetValue(0)
            self.pySpinCamera.OffsetY.SetValue(0)
            self._camROI = None
        else :
            self.stopAcquisition()
            self.pySpinCamera.OffsetX.SetValue(0)
            self.pySpinCamera.OffsetY.SetValue(0)
            self.pySpinCamera.Width.SetValue(int(camROI[2]))
            self.pySpinCamera.Height.SetValue(int(camROI[3]))
            self.pySpinCamera.OffsetX.SetValue(int(camROI[0]))
            self.pySpinCamera.OffsetY.SetValue(int(camROI[1]))
            self._camROI = camROI
            self.startAcquisition()
            
    @property
    def camROI(self) :
        if self.cameraConnected and hasattr(self, 'pySpinCamera'):
            x_size = self.pySpinCamera.Width.GetValue()
            y_size = self.pySpinCamera.Height.GetValue()
            x_offset = self.pySpinCamera.OffsetX.GetValue()
            y_offset = self.pySpinCamera.OffsetY.GetValue()
            self._camROI = [x_offset, y_offset, x_size, y_size]
        return self._camROI

    @camROI.setter
    def camROI(self, val):
        self.setCamROI(val)

    def grabArray(self) :
        if not(self.cameraConnected) :
            return False
            
        if self._triggerMode == 1 :
            self.pySpinCamera.TriggerSoftware.Execute()
            
        try : 
            pySpinImage = self.pySpinCamera.GetNextImage(2000)
            
            if pySpinImage.IsIncomplete() :
                print('WARNING ! : Camera grab image is incomplete : ', pySpinImage.GetImageStatus())
                pySpinImage.Release()
                return False
                
            if self.imageBitDepth <= 8 :
                processedImage = self.pySpinImageProcessor.Convert(pySpinImage, PySpin.PixelFormat_Mono8)
            else :
                processedImage = self.pySpinImageProcessor.Convert(pySpinImage, PySpin.PixelFormat_Mono16)
                
            img_array = processedImage.GetNDArray()
            img_array = np.array(img_array, copy=True)
            pySpinImage.Release()
            
            if hasattr(self, 'imageBitsToShift') and self.imageBitsToShift > 0 :
                img_array = np.right_shift(img_array, self.imageBitsToShift)
                
            if self.cameraConfig['reversedAxes'][0] :
                img_array = np.flip(img_array, axis=1)
            if self.cameraConfig['reversedAxes'][1] :
                img_array = np.flip(img_array, axis=0)
                
            return img_array
            
        except PySpin.SpinnakerException as ex :
            print('ERROR ! : Camera grab failed with SpinnakerException : ', ex)
            return False


class Chameleon3Class(FLIRPySpinClass) :
    def __init__(self, cameraNumber, triggerMode=0, exposurems=1, 
                 gaindB=1, camROI=None, loadDefault = False) :	
        super().__init__(cameraNumber, triggerMode=triggerMode, exposurems=exposurems,
                         gaindB=gaindB, camROI=camROI, loadDefault=loadDefault)

    def __del__(self) : 
        super().__del__()