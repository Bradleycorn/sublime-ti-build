import sublime
import sublime_plugin
import json
import subprocess
from os.path import expanduser

class TitaniumCommand(sublime_plugin.WindowCommand):

    def run(self, *args, **kwargs):
        settings = sublime.load_settings('Titanium.sublime-settings')
        self.appc               = settings.get("appceleratorPath", "/usr/local/bin/appc")
        self.loggingLevel       = settings.get("loggingLevel", "info")
        self.androidKeystore    = settings.get("androidKeystore", "")
        self.useProjectNames    = settings.get("useProjectNames", False)
        self.appcUser           = settings.get("appceleratorUsername", "")
        self.appcPass           = settings.get("appceleratorPassword", "")
        self.iosBuildFamily     = settings.get("iosBuildFamily", False)


        #Options for the various dialogs that the user chooses from to create the build command
        self.platforms = ["android", "ios", "mobileweb", "clean"]
        self.iosTargets = ["simulator", "device", "dist-appstore", "dist-adhoc"]
        self.iosFamilies = [ "universal", "iphone", "ipad"]
        self.androidTargets = ["emulator", "device", "distribution"]
        self.webTargets = ["development", "production"]

        self.buildOpts = []

        self.multipleFolders = False
        self.projectFolder = ""
        self.projectSDK = ""
        self.keystorePassword = ""
        self.keyAlias         = ""
        self.deviceID = ""
        self.androidEmulators = []
        self.androidDevices = []
        self.iosSimulators = []
        self.iosDevices = []
        self.iosDeveloperCertificates = []
        self.iosDeveloperProvisioning = []
        self.iosDistributionCertificates = []
        self.iosDistributionProvisioning = []
        self.iosAdhocProvisioning = []

        if (self.appcUser == ""):
            self.show_input_panel("Appcelerator Username", self.appcUser, self.set_appc_username, self.cancel)
        elif (self.appcPass == ""):
            self.show_input_panel("Appcelerator Password", self.appcPass, self.set_appc_password, self.cancel)
        else:
            #Prompt the user to select a project, and set the project info (folder, sdk, etc) accordingly
            self.load_project()


    #-------------------------------------------------------
    # 0. SET APPCELERATOR ACCOUNT INFO
    #    Prompts for the appcelerator username/password
    #-------------------------------------------------------
    def set_appc_username(self, value):
        if value == "":
            return

        self.appcUser = value
        if (self.appcPass == ""):
            self.show_input_panel("Appcelerator Password", self.appcPass, self.set_appc_password, self.cancel)
        else:
            #Prompt the user to select a project, and set the project info (folder, sdk, etc) accordingly
            self.load_project()

    def set_appc_password(self, value):
        if value == "":
            return

        self.appcPass = value
        #Prompt the user to select a project, and set the project info (folder, sdk, etc) accordingly
        self.load_project()



    #-------------------------------------------------------
    # 1. LOAD PROJECT
    #    Select the project folder and load environment info
    #-------------------------------------------------------
    
    def load_project(self):
        self.projectFolder = ""
        folders = self.window.folders()
        if len(folders) <= 0:
            self.show_quick_panel(["ERROR: Must have a project open"], None)
        else:
            if len(folders) == 1:
                self.multipleFolders = False
                self.projectFolder = folders[0]
                self.load_project_complete()
            else:
                self.multipleFolders = True
                if self.useProjectNames == True:
                    projectFolders = self.get_project_folders()
                    projectNames = []
                    for val in projectFolders:
                        projectNames.append(val['name'])
                    self.pick_project_name(projectNames)
                else:
                    self.pick_project_folder(folders)
    
    def load_project_complete(self):
        #If the project folder is not set, there was an error, or the "most recent configuration" option was selected
        if self.projectFolder == "":
            return

        self.projectSDK = self.load_sdk_version()


        #Now load the environment info (available devices, certificates, emulators, etc)
        self.load_environment_info()


        #Choose Which Platform to build for
        self.pick_platform()


    #Load Project Dialogs
    #--------------------

    #Shows a dialog containing the list of currently open projects (by name)
    def pick_project_name(self, projects):
        # only show most recent when there is a command stored
        if 'titaniumMostRecent' in globals():
            projects.insert(0, 'most recent configuration')

        self.show_quick_panel(projects, self.select_project_name)

    #Sets the projectFolder that will be the build target based on the name of the project the user selected
    def select_project_name(self, select):
        if select < 0:
            return

        # if most recent was an option, we need subtract 1
        # from the selected index to match the folders array
        # since the "most recent" option was inserted at the beginning
        if 'titaniumMostRecent' in globals():
            select = select - 1

        if select == -1:
            self.window.run_command("exec", titaniumMostRecent)
        else:
            projectFolders = self.get_project_folders()
            self.projectFolder = projectFolders[select]['path']
            self.load_project_complete()

    #Shows a dialog containing the list of currently open projects (by folder)
    def pick_project_folder(self, folders):
        folderNames = []
        for folder in folders:
            index = folder.rfind('/') + 1
            if index > 0:
                folderNames.append(folder[index:])
            else:
                folderNames.append(folder)

        # only show most recent when there is a command stored
        if 'titaniumMostRecent' in globals():
            folderNames.insert(0, 'most recent configuration')

        self.show_quick_panel(folderNames, self.select_project_folder)

    #Sets the projectFolder that will be the build target based on the project folder the user selected
    def select_project_folder(self, select):
        folders = self.window.folders()
        if select < 0:
            return

        # if most recent was an option, we need subtract 1
        # from the selected index to match the folders array
        # since the "most recent" option was inserted at the beginning
        if 'titaniumMostRecent' in globals():
            select = select - 1

        if select == -1:
            self.window.run_command("exec", titaniumMostRecent)
        else:
            self.projectFolder = folders[select]
            self.load_project_complete()


    #-------------------------------------------------------------------------------------
    # 2. PICK PLATFORM
    #    Select the Platform to build for, then start down the platform build options path
    #-------------------------------------------------------------------------------------

    #Shows a dialog containing the different platforms (android, ios, mobileweb) that the user can build for
    def pick_platform(self):
        # only show most recent when there are NOT multiple top level folders
        # and there is a command stored
        if self.multipleFolders == False and 'titaniumMostRecent' in globals():
            self.platforms.insert(0, 'most recent configuration')

        self.show_quick_panel(self.platforms, self.select_platform)

    #Sets the platform to build the project for (android, ios, mobileweb) based on the user's choice
    def select_platform(self, select):
        if select < 0:
            return
        self.platform = self.platforms[select]

        #Now that we know that platform the user is building for, we can set additional build options
        if self.platform == "most recent configuration":
            self.window.run_command("exec", titaniumMostRecent)
        elif self.platform == "clean":
            self.window.run_command("exec", {"cmd": [self.appc, "ti", "clean", "--username", self.appcUser, "--password", self.appcPass, "--no-banner", "--no-colors", "--project-dir", self.projectFolder]})
        else:
            self.set_build_options()        

    #Based on the platform being built for, starts the process of showing various build options
    #This function will show an input panel, and will then call a platform specific callback in the form:
    #select_<platform>_target
    def set_build_options(self):
        if self.platform == "ios":
            if len(self.iosDistributionProvisioning) < 1:
                self.iosTargets.remove('dist-appstore')
            if len(self.iosAdhocProvisioning) < 1:
                self.iosTargets.remove('dist-adhoc')

            self.show_quick_panel(self.iosTargets, self.select_ios_target)
        elif self.platform == "android":
            self.show_quick_panel(self.androidTargets, self.select_android_target)
        elif self.platform == "mobileweb":
            self.show_quick_panel(self.webTargets, self.select_mobileweb_target)


    #--------------------------------------------------------------
    # 3. ANDROID METHODS & BUILD OPTIONS
    #    Show dialogs and set options for android platform builds
    #--------------------------------------------------------------

    def select_android_target(self, select):
        if select < 0:
            return
        self.target = self.androidTargets[select]
        self.deviceID = ""

        if (self.target == "emulator"):
            self.load_android_emulator_options()
            self.show_quick_panel(self.emulatorOptions, self.select_android_emulator)
        elif (self.target == "distribution"):
            self.target = "dist-playstore"
            if self.androidKeystore == "":
                self.show_input_panel("Path to your keystore", self.androidKeystore, self.set_android_keystore, self.cancel)
            else:
                self.show_input_panel("Keystore password", self.keystorePassword, self.set_android_keystore_password, self.cancel)
        else: 
            #self.target == device
            if (len(self.androidDevices) == 1):
                self.deviceID = self.androidDevices[0]["id"]
                self.android_options_complete()
            else:
                self.load_android_device_options()
                self.show_quick_panel(self.deviceOptions, self.select_android_device)

    def android_options_complete(self):
        buildOpts = []

        if self.deviceID != "":
            buildOpts.extend(["--device-id", self.deviceID])

        if self.target == "dist-playstore":
            project_version = self.get_project_version()
            output_folder = self.projectFolder + "/dist/" + project_version
            buildOpts.extend(["--keystore", self.androidKeystore, "--store-password", self.keystorePassword, "--alias", self.keyAlias, "--output-dir", output_folder])

        self.run_titanium(buildOpts)

    # EMULATOR BUILD PATH    
    def select_android_emulator(self, select):
        if select < 0:
            return
        self.deviceID = "\"" + self.emulatorOptions[select][0] + "\""
        self.android_options_complete()


    #PLAYSTORE BUILD PATH
    def set_android_keystore(self, select):
        if select == "":
            return
        self.androidKeystore = select
        self.show_input_panel("Keystore password", self.keystorePassword, self.set_android_keystore_password, self.cancel)

    def set_android_keystore_password(self, select):
        if select == "":
            return
        self.keystorePassword = select
        self.show_input_panel("Key Alias", self.keyAlias, self.set_android_key_alias, self.cancel)

    def set_android_key_alias(self, select):
        if select == "":
            return
        self.keyAlias = select
        self.android_options_complete()

    #DEVICE BUILD PATH    
    def select_android_device(self, select):
        if select == "":
            return
        self.deviceID = self.deviceOptions[select][1]
        self.android_options_complete()
    

    # Android Helpers
    #----------------

    def load_android_emulator_options(self):
        self.emulatorOptions = []
        for obj in self.androidEmulators:
            subtitle = "Android " + obj["sdk-version"] + " (" + obj["type"] + ")"
            self.emulatorOptions.append([obj["name"], subtitle])

    def load_android_device_options(self):
        self.deviceOptions = []
        for obj in self.androidDevices:
            name = obj["brand"] + " " + obj["manufacturer"] + " (" + obj["model"] + ") Android " + obj["release"]
            self.deviceOptions.append([name, obj["id"]])



    #--------------------------------------------------------------
    # 3. IOS METHODS & BUILD OPTIONS
    #    Show dialogs and set options for ios platform builds
    #--------------------------------------------------------------

    def select_ios_target(self, select):
        if select < 0:
            return
        self.target = self.iosTargets[select]
        if self.target == "simulator":
            self.load_ios_simulator_options()
            self.show_quick_panel(self.emulatorOptions, self.select_ios_simulator)
        elif self.iosBuildFamily != False and self.iosBuildFamily in self.iosFamilies:
            self.select_ios_family(self.iosFamilies.index(self.iosBuildFamily))
        else:
            #Go ahead and pick a family to build for, then we'll choose a build path
            self.show_quick_panel(self.iosFamilies, self.select_ios_family)

    #For all targets other than simulator, 
    #the next step is to choose a family (iphone, ipad, universal).
    #After the family is selected, we'll then start down an appropriate build path
    def select_ios_family(self, select):
        if select < 0:
            return
        self.family = self.iosFamilies[select]

        if (self.target == "device"):
            self.filter_ios_devices()
            if len(self.filteredIosDevices) < 1:
                return
            elif len(self.filteredIosDevices) == 1:
                self.select_ios_device(0)
            else:
                self.show_quick_panel(self.filteredIosDevices, self.select_ios_device)
        else:
            self.pick_ios_certificate()

    def ios_options_complete(self):
        buildOpts = []

        if self.deviceID !=  "":
            buildOpts.extend(["--device-id", self.deviceID])

        if self.target == "device":
            buildOpts.extend(["--device-family", self.family, "--developer-name", self.iosCert, "--pp-uuid", self.iosProvisioningProfile])

        if self.target == "dist-appstore" or self.target == "dist-adhoc":
            project_version = self.get_project_version()
            output_folder = self.projectFolder + "/dist/" + project_version
            buildOpts.extend(["--device-family", self.family, "--distribution-name", self.iosCert, "--pp-uuid", self.iosProvisioningProfile, "--output-dir", output_folder])

        self.run_titanium(buildOpts)


    #SIMULATOR BUILD PATH
    def select_ios_simulator(self, select):
        if select < 0:
            return
        self.deviceID = "\"" + self.emulatorOptions[select][1] + "\""
        self.ios_options_complete()


    #DEVICE BUILD PATH
    def select_ios_device(self, select):
        if select < 0:
            return

        self.deviceID = "\"" + self.filteredIosDevices[select][1] + "\""
        self.pick_ios_certificate()

    #DEVICE & DIST BUILD PATH
    def pick_ios_certificate(self):
        if self.target == "device":
            self.load_ios_cert_options(self.iosDeveloperCertificates)
        else:
            self.load_ios_cert_options(self.iosDistributionCertificates)

        if len(self.certOptions) < 1:
            return
        elif len(self.certOptions) == 1:
            self.select_ios_certificate(0)
        else:
            self.show_quick_panel(self.certOptions, self.select_ios_certificate)


    def select_ios_certificate(self, select):
        if select < 0:
            return

        self.iosCert = "\"" + self.certOptions[select][1] + "\""
        self.pick_ios_provisioning_profile()

    def pick_ios_provisioning_profile(self):
        if self.target == "device":
            self.load_ios_provisioning_profile_options(self.iosDeveloperProvisioning)
        elif self.target == "dist-appstore":
            self.load_ios_provisioning_profile_options(self.iosDistributionProvisioning)
        else:
            self.load_ios_provisioning_profile_options(self.iosAdhocProvisioning)

        if len(self.provisioningProfiles) < 1:
            return
        elif len(self.provisioningProfiles) == 1:
            self.select_ios_provisioning_profile(0)
        else:
            self.show_quick_panel(self.provisioningProfiles, self.select_ios_provisioning_profile)

    def select_ios_provisioning_profile(self, select):
        if select < 0:
            return

        self.iosProvisioningProfile = self.provisioningProfiles[select][1]
        self.ios_options_complete()


    # iOS Helpers
    #------------
    def load_ios_simulator_options(self):
        self.emulatorOptions = []
        for obj in self.iosSimulators:
            title = obj["deviceType"] + " - iOS " + obj["ios"]
            if (obj["retina"] == True and obj["tall"] == False):
                title += " (retina)"
            elif (obj["retina"] == True and obj["tall"] == True):
                title += " (retina tall)"
            elif (obj["retina"] == False and obj["tall"] == True):
                title += " (tall)"

            self.emulatorOptions.append([title, obj["udid"]])

    def filter_ios_devices(self):
        self.filteredIosDevices = []
        for obj in self.iosDevices:
            if self.family != "universal" and "deviceClass" in obj and obj["deviceClass"] != self.family:
                continue

            name = obj["name"]
            if 'deviceClass' in obj:
                name = obj["deviceClass"] + " - " + name
            if 'productType' in obj:
                name += " (" + obj["productType"] + ")"
            if 'productVersion' in obj:
                name += " iOS " + obj["productVersion"]
            self.filteredIosDevices.append([name, obj["udid"]])

    def load_ios_cert_options(self, certArray): 
        self.certOptions = []
        for obj in certArray:
            self.certOptions.append([obj["fullname"], obj["name"]])

    def load_ios_provisioning_profile_options(self, profileArray):
        self.provisioningProfiles = []
        for obj in profileArray:
            name = obj["name"] + " (" + obj["appId"] + ")"
            self.provisioningProfiles.append([name, obj["uuid"]])


    #---------------------------------------------------------------
    # 3. MOBILE WEB METHODS & BUILD OPTIONS
    #    Show dialogs and set options for mobile web platform builds
    #---------------------------------------------------------------

    def select_mobileweb_target(self, select):
        if select < 0:
            return
        self.target = "web"
        self.run_titanium(["--deploy-type", self.webTargets[select]])


    #---------------------------------------------------------------------------
    # HELPER METHODS
    # These functions are helpers that other methods use to get/set data
    #---------------------------------------------------------------------------

    def show_quick_panel(self, options, done):
        #SublimeText3 requires a timeout before showing an input window
        sublime.set_timeout(lambda: self.window.show_quick_panel(options, done), 10)

    def show_input_panel(self, caption, text, done, cancel):
        #SublimeText3 requires a timeout before showing an input window
        sublime.set_timeout(lambda: self.window.show_input_panel(caption, text, done, None, cancel), 10)

    def get_project_folders(self):
        project = self.window.project_data()
        return project['folders']

    def cancel(self):
        #don't do anything
        return

    def get_project_version(self):
        process = subprocess.Popen([self.appc, "ti", "project", "version", "--username", self.appcUser, "--password", self.appcPass, "--project-dir", self.projectFolder, "--output=text", "--no-banner"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, error = process.communicate()
        return result.decode('utf-8').rstrip('\n')

    def run_titanium(self, options=[]):
        cmd = [self.appc, "run", "--username", self.appcUser, "--password", self.appcPass, "--sdk", self.projectSDK, "--project-dir", self.projectFolder, "--no-colors", "--no-banner", "--platform", self.platform, "--log-level", self.loggingLevel, "--target", self.target]
        cmd.extend(options)
        print("RUNNING COMMAND")
        print(' '.join(cmd))
        execCMD = {"cmd": ' '.join(cmd), "shell": True}

        # save most recent command
        global titaniumMostRecent
        titaniumMostRecent = execCMD

        self.window.run_command("exec", execCMD)

    #Uses appc ti project to figure out which Titanium SDK the targeted project uses
    def load_sdk_version(self):
        sublime.status_message("Getting SDK version...")

        process = subprocess.Popen([self.appc, "ti", "project", "sdk-version", "--username", self.appcUser, "--password", self.appcPass, "--project-dir", self.projectFolder, "--output=text", "--no-banner"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, error = process.communicate()

        sublime.status_message("")

        return result.decode('utf-8').rstrip('\n')
    
    #Uses appc info to get info about the various devices, emulators, certificates, sdk's and such that are installed
    def load_environment_info(self):
        sublime.status_message("Loading Build Environment Information...")
        process = subprocess.Popen([self.appc, "ti", "info", "--username", self.appcUser, "--password", self.appcPass, "-o", "json", "--no-banner"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, error = process.communicate()
        info = json.loads(result.decode('utf-8'))


        self.androidEmulators = info["android"]["emulators"]
        self.androidDevices = info["android"]["devices"]
        self.iosSimulators = []
        self.iosDevices = []
        self.iosDeveloperCertificates = []
        self.iosDeveloperProvisioning = []
        self.iosDistributionCertificates = []
        self.iosDistributionProvisioning = []
        self.iosAdhocProvisioning = []

        for device in info["ios"]["devices"]:
            self.iosDevices.append(device)

        for name, arr in list(info["ios"]["simulators"].items()):
            for sim in arr:
                self.iosSimulators.append(sim)

        for cert in info["ios"]["certs"]["keychains"][expanduser("~") + "/Library/Keychains/login.keychain"]["developer"]:
            if cert['expired'] is False:
                #maybe this needs to be l.append([cert])
                self.iosDeveloperCertificates.append(cert)

        for cert in info["ios"]["certs"]["keychains"][expanduser("~") + "/Library/Keychains/login.keychain"]["distribution"]:
            if cert['expired'] is False:
                #maybe this needs to be l.append([cert])
                self.iosDistributionCertificates.append(cert)

        for profile in info["ios"]["provisioning"]["development"]:
                if profile['expired'] is False:
                    self.iosDeveloperProvisioning.append(profile)

        for profile in info["ios"]["provisioning"]["distribution"]:
                if profile['expired'] is False:
                    self.iosDistributionProvisioning.append(profile)

        for profile in info["ios"]["provisioning"]["adhoc"]:
                if profile['expired'] is False:
                    self.iosAdhocProvisioning.append(profile)

        sublime.status_message("")
