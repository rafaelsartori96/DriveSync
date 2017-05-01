import os
import io
import atexit
import sched
import httplib2
import webbrowser
import configparser

from apiclient import discovery
from oauth2client import tools
from oauth2client import client
from oauth2client.file import Storage

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

class Configuration:
    def __init__(self, configurationDirectory):
        self.sectionName = 'DEFAULT'
        self.configuration = configparser.ConfigParser()
        self.configurationFile = os.path.join(configurationDirectory, 'configuration.ini')
        # Writing default configuration file
        if not os.path.exists(self.configurationFile):
            self.configuration[self.sectionName] = {
                'drive-directory': "~/DriveSync",
                'sync-interval-seconds': 120
            }

    def __contains__(object, index):
        return index in object.configuration[object.sectionName]

    def __getitem__(object, index):
        return object.configuration[object.sectionName][index]

    def __setitem__(object, index, value):
        object.configuration[object.sectionName][index] = value

    def saveConfiguration(self):
        with open(str(self.configurationFile), 'w') as fileWriter:
            self.configuration.write(fileWriter)
            print('Wrote default configuration file on ' + self.configurationFile)

    def readConfiguration(self):
        self.configuration.read(self.configurationFile)

class DriveSync:
    def __init__(self):
        self.homeDirectory = os.path.expanduser('~')
        self.configurationDirectory = os.path.join(self.homeDirectory, '.drivesync')

        # Creating app directory if it doesn't exists
        if not os.path.exists(self.configurationDirectory):
            os.makedirs(self.configurationDirectory)
            print('Created DriveSync configuration folder on ' + self.configurationDirectory)

        self.configuration = Configuration(self.configurationDirectory)
        self.drivesyncDirectory = os.path.expanduser(self.configuration['drive-directory'])

        # Searching DriveSync directory
        if not os.path.exists(self.drivesyncDirectory):
            os.makedirs(self.drivesyncDirectory)
            print('Created DriveSync directory on ' + self.drivesyncDirectory)
        else:
            print('Using ' + self.drivesyncDirectory + ' as DriveSync folder')

        atexit.register(self.stopSynchronizationTask)
        self.synchronizationInterval = int( self.configuration['sync-interval-seconds'])
        # Force sync (this will register a task)
        self.scheduler = sched.scheduler()
        self.scheduler.enter(delay=0, priority=1, action=self.doSynchronizationTask)
        try:
            print('=== DriveSync initialized!')
            self.scheduler.run(blocking=True)
        except (KeyboardInterrupt, SystemExit):
            print('Application interrupted.')

    def getAuthenticatedService(self):
        self.credentialFilePath = os.path.join(self.configurationDirectory, 'drivesync-credentials.json')

        # Creating storage on credential file
        storage = Storage(self.credentialFilePath)
        credentials = storage.get()
        if not credentials or credentials.invalid:
            # Enable the API through developer id, asking for all privileges
            flow = client.flow_from_clientsecrets('client_secret.json', scope='https://www.googleapis.com/auth/drive')
            flow.user_agent = 'drive-sync-id'

            # Running permissions on Google
            if flags:
                credentials = tools.run_flow(flow, storage, flags)
            else: # Needed only for compatibility with Python 2.6
                credentials = tools.run(flow, storage)

            # Printing success
            print('Stored Google credentials on ' + self.credentialFilePath)

        # Create and return service
        http = credentials.authorize(httplib2.Http())
        return (discovery.build('drive', 'v3', http=http), http)

    def stopSynchronizationTask(self):
        # This will auto-trigger on exit
        print('Stopped synchronization thread')

    def doSynchronizationTask(self):
        print('-> Synchronizing...')
        somethingChanged = False

        idIndex = {}
        parentFileDict = {}
        pageToken = None
        while True:
            googleService, http = self.getAuthenticatedService()
            response = googleService.files().list(q="mimeType == 'application/vnd.google-apps.folder' and not trashed",
                                                 spaces='drive',
                                                 fields='nextPageToken, files(id, name, mimeType, parents)',
                                                 pageToken=pageToken).execute(http=http)
            for file in response.get('files', []):
                driveFile = DriveFile(file)

                idIndex[driveFile.id] = driveFile

                if driveFile.parent not in parentFileDict:
                    parentFileDict[driveFile.parent] = [driveFile]
                else:
                    parentFileDict[driveFile.parent] += [driveFile]
            pageToken = response.get('nextPageToken', None)
            if pageToken is None:
                break;

        for parent, fileList in parentFileDict.items():
            print(idIndex[parent].name + ': ' + str(fileList))

        if somethingChanged:
            print('-> Synchronized with Google Drive!')
        else:
                print('-> Nothing changed.')

        # Repeat task
        self.scheduler.enter(delay=self.synchronizationInterval, priority=1, action=self.doSynchronizationTask)

class DriveFile:
    def __init__(self, file):
        self.id = file.get('id')
        self.name = file.get('name')
        self.type = file.get('mimeType'),
        self.parent = file.get('parents', ['unknown'])[0]

    def __str__(self):
        return self.fileName

    def __iter__(self):
        return [self.id, self.name]

def main():
    print("=== DriveSync v0.1, by Rafael 'jabyftw' Santos ===")
    driveSync = DriveSync()

if __name__ == '__main__':
    main()
