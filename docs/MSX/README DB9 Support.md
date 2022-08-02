A new option has been added in the OSD menu of this core called "UserIO Joystick" that allows playing with joysticks of Mega Drive/Genesis (DB9) or Neo-Geo/Supergun (DB15). This new feature is disabled by default, therefore you must enter the menu (F12) the first time to activate it and save the config if you want to keep it on for the next time.

This core is updated at the same rate as the official core, therefore, it preserves the same functionalities, and also adds the possibility of directly connecting DB9 and DB15 joysticks.

For controlling everything with the UserIO Joysticks (including the OSD menu), is also needed to update the files: MiSTer and menu.rbf from the root of the SD card. The link to these files is here (download the latest release):

MiSTer_Main: 
https://github.com/MiSTer-DB9/Main_MiSTer/tree/master/releases

Core Menu:
https://github.com/MiSTer-DB9/Menu_MiSTer/tree/master/releases


Menu control from DB9 joystick: 
Start+C-> Show OSD menu  |  A-> Enter  |  B-> Esc


Download the new updater script to always have all the cores updated, for this you must place the following file in the path "/Scripts/update.sh" of the SD card. When running it from your MiSTer you will download the official versions of all cores but, if there is a DB9 version available, you'll download the improved DB9 version instead. The first time this script is launched, the process will be slower because it will do a general update. 

Download the updater script from this link:
https://raw.githubusercontent.com/theypsilon/Updater_script_MiSTer_DB9/master/update.sh


Also you can get more information about DB9 fork from this link: 
https://github.com/antoniovillena/MiSTer_DB9.git
