##############################################################################################################################
# Script to support feature variation fonts in a fontmake workflow
# version 2.0
# - Refactored code
# - Now properly duplicates all kerning when rvrn glyphs are added

# Converts input glyphs file with bracket layers into a form with suffixed glyphs so that fontmake can generate a VF
# Uses the parsed bracket values to generate a script to run on the final ttf using fonttools to enable the GSUB feature
##############################################################################################################################

# TODO
## Support cases where a glyph has more than one substitution (though I don't think Glyphs currently supports this)
## Number the suffixes when a glyph has more than one substitution

import sys
import os
import re
import copy
import time
from glyphsLib import GSFont
from glyphsLib import GSGlyph
from glyphsLib import GSLayer
from glyphsLib import GSComponent
from glyphsLib.glyphdata import get_glyph

suffix = ".rvrn"

def parseOpenType(objects, listObjects, splitter):
    '''
    Splits each class, feature, featurePrefix, etc. into an array based on a given character.
    This array is then added to an overall array for all classes, features or feature prefixes
    '''
    for thisObject in objects:
        addObject = thisObject.code.split(splitter)
        listObjects.append(addObject)
    return listObjects



def getVfOrigin(font):
    '''
    Sets VfOrigin based on Glyphs custom parameter if present.
    Otherwise use first master as VfOrigin
    '''
    if font.customParameters["Variation Font Origin"] != None:
        VfOrigin = font.customParameters["Variation Font Origin"]
    elif font.customParameters["Variable Font Origin"] != None:
        VfOrigin = font.customParameters["Variable Font Origin"]
    else:
        VfOrigin = font.masters[0].id
    
    print "Variable Font Origin is:", font.masters[VfOrigin].name, "\n"
    return VfOrigin



def getAxes(font):
    '''
    Creates a dictionary for all axes in the font based on Glyphs custom parameter.
    Each entry contains another dictionary for tag, min/max/default, and scaled values
    '''
    global doNotSave
    fontAxes = {}
    try:
        for axisIndex, axis in enumerate(font.customParameters["Axes"]):
            fontAxes.update({'axis%s' % str(axisIndex + 1) : {'min': 100000, 'max': -1000000, 'tag': axis['Tag']}})
    except:
        print "Could't detect axes. Font lacks custom parameter \'Axes\'\n"
        doNotSave = True
    return fontAxes



def getAxisValue(object, axisIndex):
    '''
    Takes an axis index and maps it to the correct value.
    This will most likely change in Glyphs 3.0
    '''
    if axisIndex == 0:
        axisValue = object.weightValue
    elif axisIndex == 1:
        axisValue = object.widthValue
    elif axisIndex == 2:
        axisValue = object.customValue
    elif axisIndex == 3:
        axisValue = object.customValue1
    elif axisIndex == 4:
        axisValue = object.customValue2
    elif axisIndex == 5:
        axisValue = object.customValue3
    else:
        print "Error axis index %s out of range" % axisIndex
        return None
    return axisValue



def getMasterRange(master, axisIndex, axis, VfOrigin):
    '''
    Checks master values against those in the fontAxes dict
    Updates values accordingly
    '''
    axisValue = getAxisValue(master, axisIndex)
    print axisValue

    if master.id == VfOrigin:
        axis.update({'def': axisValue})
    if axisValue > axis['max']:
        axis.update({'max': axisValue})
    if axisValue < axis['min']:
        axis.update({'min': axisValue})



def getInstanceValues(instance, axisIndex, axis, weightDict):
    '''
    Checks instances and updates axis dict with scaled min/max values
    '''
    if instance.active == True:
        axisValue = getAxisValue(instance, axisIndex)

        if axis['tag'] == 'wght':
            if instance.customParameters["weightClass"] != None:
                scaledValue = instance.customParameters["weightClass"]
            else:
                scaledValue = weightDict[instance.weight]
        else:
            scaledValue = axisValue

        if axisValue == axis['min']:
            axis.update({'sMin': scaledValue})
        elif axisValue == axis['max']:
            axis.update({'sMax': scaledValue})



def parseAxesValues(font, fontAxes, VfOrigin, weightDict):
    '''
    Uses information from masters and instances to add information for each axis.
    Adds scaled values as well as mapped values
    '''
    axisCount = 0
    for axisIndex, axis in fontAxes.items():
        axisIndex = int(re.sub('axis', '', axisIndex)) - 1
        axisCount = axisIndex
        for master in font.masters:
            getMasterRange(master, axisIndex, axis, VfOrigin)

        for instance in font.instances:
            getInstanceValues(instance, axisIndex, axis, weightDict)

        percent = (axis['def'] - axis['min']) / (axis['max'] - axis['min'])
        sDef = ((axis['sMax'] - axis['sMin']) * percent) + axis['sMin']
        axis.update({'sDef': sDef})


    if axisCount + 1 > 1:
        print "Detected %s Axes" % (axisCount + 1)
        print "Parsed Axes values:"
    else:
        print "Detected %s Axis" % (axisCount + 1)
        print "Parsed Axis values:"

    for axisIndex, axis in fontAxes.items():
        print fontAxes
        print "%s\tMin=%s\tDefault=%s\tMax=%s" % (axis['tag'], axis['min'], axis['def'], axis['max'])
    print "\n"



def getBracketGlyphs(font, needsDup, logged, noComponents):
    '''
    Recursively goes through all glyphs.
    If there is a bracket layer, or a component with a bracket layer, add glyph to needsDup
    '''
    # No glyphs are marked for duplication yet
    newAddition = False

    # Go through all glyphs in font
    for glyph in font.glyphs:
        # If the glyphs has NOT been marked for duplication check layers
        if logged.get(glyph.name) == None and noComponents.get(glyph.name) == None:
            # Iterate through all layers
            for layer in glyph.layers:
                # If glyph has been marked for duplication break the loop else proceed
                if logged.get(glyph.name) != None:
                    break
                else:
                    # If active bracket layer mark for duplication and move to next glyph
                    if re.match('.*\d\]$', layer.name) != None:
                        needsDup.append(glyph.name)
                        logged.update({glyph.name: True})
                        newAddition = True
                        break
                    else:
                        if len(layer.components) == 0:
                            noComponents.update({glyph.name : True})
                        else:
                            # Check components
                            for component in layer.components:
                                # If component is not logged proceed
                                if logged.get(component.name) == None:
                                    pass
                                # If component references a glyph marked for duplication then mark this glyph as well
                                else:
                                    needsDup.append(glyph.name)
                                    logged.update({glyph.name: True})
                                    newAddition = True
                                    break
        # Skip glyph if it has already been marked for duplication
        else:
            pass

    # If a new glyph was marked check all glyphs and components again
    if newAddition == True:
        return getBracketGlyphs(font, needsDup, logged, noComponents)
    else:
        # When finished print glyphs duplicated
        print "Duplicated %s glyphs for GSUB rvrn feature:" % str(len(needsDup))
        return needsDup



def normalizeValues(location, fontAxes):
    '''
    Takes a GSUB location as a list and normalize the values (pre-user mapped). Last two list items are not normalized sinze they are not axes values
    '''
    for value in range(len(location) - 2):
        if location[value] > fontAxes['axis' + str(value + 1)]['max'] or location[value] < fontAxes['axis' + str(value + 1)]['min']:
            location[value] = None
        if location[value] != None:
            axisValue = location[value]
            rMax = fontAxes['axis' + str(value + 1)]['max']
            rMin = fontAxes['axis' + str(value + 1)]['min']
            sMax = fontAxes['axis' + str(value + 1)]['sMax']
            sMin = fontAxes['axis' + str(value + 1)]['sMin']
            # mDef = fontAxes['axis' + str(value + 1)]['mDef']
            sDef = fontAxes['axis' + str(value + 1)]['sDef']
            scaledValue = ((axisValue - rMin) / (rMax - rMin)) * (sMax - sMin) + sMin

            # Calc normalized "to" value
            if scaledValue <= sDef and sMin != sDef:
                normValue = ((scaledValue - sMin) / (sDef - sMin)) - 1
            elif scaledValue >= sDef:
                normValue = (scaledValue - sDef) / (sMax - sDef)
            else:
                print "ERROR Normalizing value %s on %s axis" % (axisValue, fontAxes['axis' + str(value + 1)]['tag'])

            location[value] = normValue

def duplicateGlyph(font, glyphName):
    '''
    Duplicates a glyph and adds a suffix to its name
    '''
    # Duplicated glyph
    dupGlyph = GSGlyph(copy.copy(font.glyphs[glyphName]))
    # Add suffix
    dupGlyph.name = glyphName + suffix

    # Add layers to duplicate glyph (now a true duplicate)
    for layer in font.glyphs[glyphName].layers:
        newLayer = GSLayer()
        newLayer.layerId = layer.layerId
        newLayer.associatedMasterId = layer.associatedMasterId
        newLayer.name = layer.name
        newLayer.paths = layer.paths
        newLayer.components
        newLayer.anchors = layer.anchors
        newLayer.width = layer.width
        for componentIndex, component in enumerate(layer.components):
            addComponent = GSComponent(layer.components[componentIndex].name)
            addComponent.alignment = layer.components[componentIndex].alignment
            addComponent.transform = layer.components[componentIndex].transform
            addComponent.anchor = layer.components[componentIndex].anchor
            addComponent.locked = layer.components[componentIndex].locked
            newLayer.components.append(addComponent)
        dupGlyph.layers.append(newLayer)

    # Remove any unicode value since these are suffixed glyphs
    dupGlyph.unicode = None

    dupGlyph.leftKerningGroup = font.glyphs[glyphName].leftKerningGroup
    dupGlyph.rightKerningGroup = font.glyphs[glyphName].rightKerningGroup

    # Add dupGlyph to font
    font.glyphs.append(dupGlyph)

    addKerns(font, dupGlyph.name, glyphName)

    return dupGlyph


def addKerns(font, dupName, origName):
    dupId = font.glyphs[dupName].id
    origId = font.glyphs[origName].id

    for masterId, masterDict in font.kerning.items():
        for leftKern, kernDict in masterDict.items():
            if re.match("@MMK", leftKern) == None and leftKern == origId:
                font.kerning[masterId].update({dupId : kernDict})
            for rightKern, value in kernDict.items():
                if re.match("@MMK", rightKern) == None and rightKern == origId:
                    font.kerning[masterId][leftKern].update({dupId : value})



def bracketIsDefault(glyph, VfOrigin):
    '''
    Determines which type of layer becomes a master layer in original glyph and which one becomes a master layer for the duplicate glyph
    If bracketDefault is True then [bracket] layers are default, else ]reverseBracket] layers are default 
    '''
    for layer in glyph.layers:
        if layer.associatedMasterId == VfOrigin:
            if re.match(".*\[.*\d\]$", layer.name) != None:
                bracketDefault = False
                break
            elif re.match(".*\].*\d\]$", layer.name) != None:
                bracketDefault = True
                break
        else:
            bracketDefault = None
    return bracketDefault



def addToClass(classes, dupGlyph, origGlyphName):
    '''
    Adds the newly duplicated glyphs for each class
    '''
    for thisClass in classes:
        for glyphName in thisClass:
            if re.match( "^" + origGlyphName + "$", glyphName) != None and re.match(".*\.rvrn", glyphName) == None:
                thisClass.append(dupGlyph.name)



def addToFeature(font, features, needsDup, dupGlyph, origGlyphName):
    '''
    Adds the newly duplicated glyphs to each feature
    '''
    for featureIndex, feature in enumerate(features):
        for line in feature:
            # If origGlyph is subbed out make a new substitution for the rvrn glyph
            if re.match("^sub " + origGlyphName + " by", line) != None:
                newLine = re.sub(" by", ".rvrn by", line)
                # Check all rvrn glyphs against what is subbed in. If there is a match the rvrn glyph is subbed in instead
                for dup in needsDup:
                    if re.match(".*by " + dup + ";", line) != None:
                        newLine = re.sub(";", ".rvrn;", newLine)
                        break
                print "Added new substitution in %s feature: %s" % (font.features[featureIndex].name, newLine)
                feature.append(newLine)



def mapLayers(font, logged, dupGlyph, origGlyphName, layer, location, bracketDefault, bracketType):
    if bracketType == "bracket":
        if bracketDefault == False:
            location.append(False)
            dupGlyph.layers[layer.associatedMasterId].paths = layer.paths
            dupGlyph.layers[layer.associatedMasterId].components = copy.copy(layer.components)
            dupGlyph.layers[layer.associatedMasterId].anchors = layer.anchors
            dupGlyph.layers[layer.associatedMasterId].width = layer.width
            for componentIndex, component in enumerate(layer.components):
                dupGlyph.layers[layer.associatedMasterId].components[componentIndex].alignment = layer.components[componentIndex].alignment
                dupGlyph.layers[layer.associatedMasterId].components[componentIndex].transform = layer.components[componentIndex].transform
                dupGlyph.layers[layer.associatedMasterId].components[componentIndex].anchor = layer.components[componentIndex].anchor
                dupGlyph.layers[layer.associatedMasterId].components[componentIndex].locked = layer.components[componentIndex].locked
                if logged.get(component.name) == None:
                    pass
                else:
                    dupGlyph.layers[layer.associatedMasterId].components[componentIndex].name = (component.name + suffix)
        else:
            location.append(True)
            font.glyphs[origGlyphName].layers[layer.associatedMasterId].paths = layer.paths
            font.glyphs[origGlyphName].layers[layer.associatedMasterId].anchors = layer.anchors
            font.glyphs[origGlyphName].layers[layer.associatedMasterId].width = layer.width
            font.glyphs[origGlyphName].layers[layer.associatedMasterId].components = copy.copy(layer.components)
    elif bracketType == "reverse":
        if bracketDefault == False:
            location.append(False)
            font.glyphs[origGlyphName].layers[layer.associatedMasterId].paths = layer.paths
            font.glyphs[origGlyphName].layers[layer.associatedMasterId].anchors = layer.anchors
            font.glyphs[origGlyphName].layers[layer.associatedMasterId].width = layer.width
            font.glyphs[origGlyphName].layers[layer.associatedMasterId].components = copy.copy(layer.components)
        else:
            location.append(True)
            dupGlyph.layers[layer.associatedMasterId].paths = layer.paths
            dupGlyph.layers[layer.associatedMasterId].anchors = layer.anchors
            dupGlyph.layers[layer.associatedMasterId].width = layer.width
            for componentIndex, component in enumerate(layer.components):
                dupGlyph.layers[layer.associatedMasterId].components[componentIndex].alignment = layer.components[componentIndex].alignment
                dupGlyph.layers[layer.associatedMasterId].components[componentIndex].transform = layer.components[componentIndex].transform
                dupGlyph.layers[layer.associatedMasterId].components[componentIndex].anchor = layer.components[componentIndex].anchor
                dupGlyph.layers[layer.associatedMasterId].components[componentIndex].locked = layer.components[componentIndex].locked
                if logged.get(component.name) == None:
                    pass
                else:
                    dupGlyph.layers[layer.associatedMasterId].components[componentIndex].name = (component.name + suffix)



def goodSubst(glyphLocations):
    '''
    Checks if the glyph has more than one GSUB region defined for an axis based on a list of locations
    '''
    global doNotSave
    checkValues = []
    for location in glyphLocations:
        for value in range(len(location) - 2):
            try:
                checkValues[value].update({location[value] : value + 1})
            except:
                checkValues.append({location[value] : value + 1})
    for value in checkValues:
        if len(value) > 1:
            print "ERROR: More than 1 substitution detected for glyph \'%s\'" % origGlyphName
            doNotSave = True
            return (checkValues, False)
        else:
            return (checkValues, True)



def setupBracketGlyphs(font, needsDup, features, classes, VfOrigin, logged, fontAxes, substitution):
    '''
    Iterates through the list of glyphs that need duplicates, maps layers to the correct glyphs, updates feature code,
    and writes entry in the addFeatureVars.py script
    '''

    # A dictionary of glyph names to GSUB locations per bracket layer
    # { "a" : [[24.0, 40.0, 5B6G-F3GHJ7J-FG68, True], [], []]}
    # { glyph.name : [axis1Value, axis2Value, axisEtc, layer.associatedMasterId, bracketDefault], [], []}
    locations = {}

    firstGlyph = True
    # Iterate through glyphs marked for duplication
    for glyphIndex, origGlyphName in enumerate(needsDup):
        # Duplicated glyph
        dupGlyph = duplicateGlyph(font, origGlyphName)

        addToClass(classes, dupGlyph, origGlyphName)
        addToFeature(font, features, needsDup, dupGlyph, origGlyphName)


        delLayer = []
        glyphLocations = []
        copiedLocations = False

        bracketDefault = bracketIsDefault(dupGlyph, VfOrigin)

        for layer in dupGlyph.layers:      
            if re.match(".*\[.*\d\]$", layer.name) != None:
                location = map(float, re.sub('(^[^][]*(\[|\]))|\]| ', '', layer.name).split(","))
                location.append(layer.associatedMasterId)

                mapLayers(font, logged, dupGlyph, origGlyphName, layer, location, bracketDefault, "bracket")

                normalizeValues(location, fontAxes)
                glyphLocations.append(location)

                # Mark layer for deletion
                delLayer.append(layer.layerId)
            elif re.match(".*\].*\d\]$", layer.name) != None:
                location = map(float, re.sub('(^[^][]*(\[|\]))|\]| ', '', layer.name).split(","))
                location.append(layer.associatedMasterId)

                mapLayers(font, logged, dupGlyph, origGlyphName, layer, location, bracketDefault, "reverse")

                normalizeValues(location, fontAxes)
                glyphLocations.append(location)

                # Mark layer for deletion
                delLayer.append(layer.layerId)
            else:
                for component in layer.components:
                    if logged.get(component.name) == None:
                        pass
                    else:
                        locations.update({origGlyphName : locations[component.name]})
                        glyphLocations = locations[component.name]
                        copiedLocations = True
                        for location in locations[component.name]:
                            if layer.layerId == location[-2]:
                                bracketDefault = location[-1]
                        component.name = (component.name + suffix)

        checkValues = goodSubst(glyphLocations)[0]
        if goodSubst(glyphLocations)[1] == True:
            substitution = generatePy(checkValues, fontAxes, firstGlyph, substitution, bracketDefault, origGlyphName)


        delLayers(font, delLayer, dupGlyph)

        # If glyph does not get locations from referenced component then add the parsed locations
        if copiedLocations == False:
            locations.update({origGlyphName : glyphLocations})

        firstGlyph = False

    return substitution



def generatePy(checkValues, fontAxes, firstGlyph, substitution, bracketDefault, origGlyphName):
    '''
    Verify that the glyph only has one substitution
    Glyphs App does not appear to support more though this script could serve as a workaround for that. Might add in the future
    '''
    for value in checkValues:
        glyphString = ""
        firstRegion = True
        axis = fontAxes["axis" + str(value.values()[0])]['tag']

        if value.keys()[0] != None and bracketDefault == False:
            if firstRegion == False:
                glyphString = glyphString + ", "
            glyphString = glyphString + ("\"%s\" : (%s, %s)" % (axis, str(value.keys()[0]), str(1.0)))
            firstRegion = False
        elif value.keys()[0] != None and bracketDefault == True:
            if firstRegion == False:
                glyphString = glyphString + ", "
            glyphString = glyphString + ("\"%s\" : (%s, %s)" % (axis, str(-1.0), str(value.keys()[0])))
            firstRegion = False

        glyphSub = "{\"%s\" : \"%s\"}" % (get_glyph(origGlyphName)[1], get_glyph(origGlyphName)[1] + suffix)
        print "([{%s}], %s)" % (glyphString, glyphSub)

        if firstGlyph == True:
            glyphString = "\t([{%s}], %s)," % (glyphString, glyphSub)
        else:
            glyphString = " \n\t([{%s}], %s)," % (glyphString, glyphSub)
        substitution = substitution + glyphString
        firstGlyph = False
    return substitution



def delLayers(font, delLayerList, dupGlyph):
    '''
    Delete layers for a glyph based on input list
    '''
    for layerId in delLayerList:
        del font.glyphs[dupGlyph.name].layers[layerId]
        origGlyph = re.sub(suffix, "", dupGlyph.name)
        del font.glyphs[origGlyph].layers[layerId]



def updateOpenType(font, objects, listObjects, joiner):
    '''
    Update OT class or feature using a joiner character (i.e. space or newline)
    '''
    for objectIndex, thisObject in enumerate(objects):
        thisObject.code = joiner.join(listObjects[objectIndex])



def saveFont(font, filename, start, substitution):
    '''
    If there are no errors, save the font file and write addFeatureVars.py
    '''
    global doNotSave
    if doNotSave == True:
        print "Encountered Error, did not save"
    else: 
        font.save(filename)
        print "File Saved\n"

        substitution = substitution + " \n] \n\naddFeatureVariations(f, condSubst)\n\nf.save(fontPath)"
        
        file = open("addFeatureVars.py", "w") 
        file.write(substitution) 
        file.close()

        end = time.time()

        print "\n\n\n"
        print "Total Time: %s seconds" % str(end - start)

def main():
    global doNotSave

    start = time.time()

    doNotSave = False

    filename = sys.argv[-1]
    font = GSFont(filename)

    # Store classes and features
    classes = parseOpenType(font.classes, [], " ")
    features = parseOpenType(font.features, [], "\n")

    # Gets number of axes and stores in a dictionary
    fontAxes = getAxes(font)

    # Set origin master to determine which layers are used in the duplicate glyph
    VfOrigin = getVfOrigin(font)

    weightDict = {
        "Thin" : 100,
        "ExtraLight" : 200,
        "UltraLight" : 200,
        "Light" : 300,
        "Normal" : 400,
        "Regular" : 400,
        "Medium" : 500,
        "DemiBold" : 600,
        "SemiBold" : 600,
        "Bold" : 700,
        "UltraBold" : 800,
        "ExtraBold" : 800,
        "Black" : 900,
        "Heavy" : 900,
        }

    # Checks all masters and updates fontAxes dictionary min/max values
    # Checks all instances and stores scaled min/def/max values
    # TODO add ability to check virtual master ranges
    parseAxesValues(font, fontAxes, VfOrigin, weightDict)

    needsDup = []
    logged = {}
    noComponents = {}

    # Recursively goes through all glyphs and determines if they will need a duplicate glyph
    needsDup = getBracketGlyphs(font, needsDup, logged, noComponents)

    substitution = "import os\nimport sys\nimport fontTools\nfrom fontTools.ttLib import TTFont\nfrom fontTools.varLib.featureVars import addFeatureVariations\n\nfontPath = sys.argv[-1]\n\nf = TTFont(fontPath)\n\ncondSubst = [\n"

    substitution = setupBracketGlyphs(font, needsDup, features, classes, VfOrigin, logged, fontAxes, substitution)

    updateOpenType(font, font.classes, classes, " ")
    updateOpenType(font, font.features, features, "\n")

    saveFont(font, filename, start, substitution)


if __name__ == "__main__":
    main()