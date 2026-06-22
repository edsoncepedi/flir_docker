# -*- coding: utf-8 -*- 

"""
Define a specific config for each camera via the camerasConfigs dictionnary
"""

camerasConfigs = [None, 
# Camera number 1
dict(name = 'FLIR A70 Thermal', # Mudamos o nome para organização
driver = 'FLIRPySpin', 
model = 'FLIRPySpin', # IMPORTANTE: Como não há uma classe específica "FLIRA70Class" no arquivo FLIRPySpin.py, usamos a classe genérica do driver
serial = 89901059, # <-- O número de série real extraído da sua imagem!
imageBitDepth = 8, 
defaultExposurems = 16.0, # Câmeras GigE costumam precisar de uma exposição inicial ligeiramente maior
defaultGaindB = 0., 
defaultTrigger = 'software', # Mudamos para software para você testar direto no código
defaultCamROI = None, 
defaultFlushSensor = True, 
defaultRemoveBackground = False, 
defaultROIkrgnames = ['MOT','',''],
pixelCalXumperpx = 1,  
pixelCalYumperpx = 1,  
reversedAxes = [False, False], 
cameraQuantumEff = 0.32, 
numericalAperture = 0.1234, 
Imaging__imagingTypeText = 'Absorption Imaging', 
Imaging__atomicMassAU = 86.909, 
Imaging__atomicFrequencyTHz = 384.23, 
Imaging__Isat = 16.693, 
Imaging__atomicLineFWHWinMHz = 6.066, 
Imaging__thresholdAbsImg = 30, 
Imaging__includeSaturationEffects = True, 
Imaging__laserPulseDurationus = 50., 
Imaging__laserIntensity = 50., 
Imaging__laserDetuningMHz = 0., 
),
# Camera number 2
dict(name = 'Thorlabs test', # Name chosen by user 
driver = 'Thorlabs', # Driver Name (usually depends  on manufacturer) : driver has to be the name of a file in Cameras folder (module)
model = 'Zelux', # Model name if model+'Class' match name of a Class defined in driver file, use specific child class otherwise use generic driver+'Class'
serial = 27640, # serial number of the camera, used to identify the camera 
imageBitDepth = 10, # set bit depth of sensor reading (Thorlabs => software auto set as default sensor bit depth) 
defaultExposurems = 0.2, # default duration of exposition (exposure) in milliseconds
defaultGaindB = 0., # 'default hardware gain (amplification) at sensor read in dB
defaultTrigger = 'external', # 'external' or 'software'
defaultCamROI = None, # (None or [int]*4) : Camera region of interest to read from sensor : None for full senseor or [x offset , y offset , x size , y size ] (binning is not implemented)
defaultFlushSensor = False, # default setting to decide to make flush read of camera before taking an image
defaultRemoveBackground = False, # default setting to decide if a background image is taken and removed to the previous ones
defaultROIkrgnames = ['MOT','',''],# try to find the [black, red, green] imaging ROIs via the names indicated here
pixelCalXumperpx = 1, #µm/pixel
pixelCalYumperpx = 1, #µm/pixel
reversedAxes = [False, False], # decide if for each axis X and Y, if it will be reversed 
cameraQuantumEff = 0.32, # at imaging wavelenght 
numericalAperture = 0.1, # sin(arctan(D/(2f)))
Imaging__imagingTypeText = 'Absorption Imaging', # 'Absorption Imaging' or 'Fluorescence Imaging' 
Imaging__atomicMassAU = 86.909, #e atom mass in atomic units
Imaging__atomicFrequencyTHz = 384.23, #transition frequency in THz
Imaging__Isat = 16.693, # W/m² effective saturation intensity : default value
Imaging__atomicLineFWHWinMHz = 6.066, # Gamma = 2 * pi * Imaging__atomTransitionFWHWinMHz * 10^6,   atomic natural linewidth in MHz (full width at half maximum in frequency)
Imaging__thresholdAbsImg = 15, # minimum measureed intensity (e per pixel) on ref frame to compute the absorption : default value
Imaging__includeSaturationEffects = True, # add correction due to saturation of atomic response to atomic density : default value
Imaging__laserPulseDurationus = 50., # laser pulse lenght used for imaging in µs : default value
Imaging__laserIntensity = 10., # laser intensity used for fluorescence imaging in W/m² or uW/mm² : default value
Imaging__laserDetuningMHz = 0., # laser detunning from resonance in fluo imaging : default value
),]

