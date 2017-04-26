import os
import io
import atexit
import sched
import httplib2
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


class DriveSync:
    def __init__(self):
        self.home_directory = os.path.expanduser('~')
        self.drivesync_config_directory = os.path.join(self.home_directory, '.drivesync')

        # Creating app directory if it doesn't exists
        if not os.path.exists(self.drivesync_config_directory):
            os.makedirs(self.drivesync_config_directory)
            print('Created DriveSync configuration folder on ' + self.drivesync_config_directory)

        self.configuration = configparser.ConfigParser()
        self.configuration_file = os.path.join(self.drivesync_config_directory, 'configuration.ini')
        # Writing default configuration file
        if not os.path.exists(self.configuration_file):
            self.configuration['DEFAULT'] = {
                'drive-directory': '' + os.path.join(self.home_directory, 'DriveSync'),
                'sync-interval-seconds': 120
            }
            with open(str(self.configuration_file), 'w') as file_writer:
                self.configuration.write(file_writer)
                print('Wrote default configuration file on ' + self.configuration_file)

        # Reading configuration file
        self.configuration.read(self.configuration_file)
        self.drivesync_directory = os.path.expanduser(self.configuration['DRIVESYNC']['drive-directory'])

        # Searching DriveSync directory
        if not os.path.exists(self.drivesync_directory):
            os.makedirs(self.drivesync_directory)
            print('Created DriveSync directory on ' + self.drivesync_directory)
        else:
            print('Using ' + self.drivesync_directory + ' as DriveSync folder')

        # Starting Google service => this will ask for credentials
        http_service = self.get_credentials().authorize(httplib2.Http())
        self.google_service = discovery.build('drive', 'v3', http=http_service)

        atexit.register(self.stop_sync_task)
        self.sync_interval = int( self.configuration['DRIVESYNC']['sync-interval-seconds'])
        # Force sync (this will register a task)
        self.scheduler = sched.scheduler()
        self.scheduler.enter(delay=0, priority=1, action=self.sync_task)
        try:
            print('=== DriveSync initialized!')
            self.scheduler.run(blocking=True)
        except (KeyboardInterrupt, SystemExit):
            print('Application interrupted.')

    def get_credentials(self):
        self.credential_file_path = os.path.join(self.drivesync_config_directory, 'drivesync-credentials.json')

        # Creating storage on credential file
        store = Storage(self.credential_file_path)
        credentials = store.get()
        if not credentials or credentials.invalid:
            # Enable the API through developer id, asking for all privileges
            flow = client.flow_from_clientsecrets('client_id.json', 'https://www.googleapis.com/auth/drive')
            flow.user_agent = 'DriveSync'

            # Running permissions on Google
            if flags:
                credentials = tools.run_flow(flow, store, flags)
            else: # Needed only for compatibility with Python 2.6
                credentials = tools.run(flow, store)

            # Printing success
            print('Storing Google credentials on ' + self.credential_file_path)
        return credentials

    def stop_sync_task(self):
        # This will auto-trigger on exit
        print('Stopped sync thread')

    def sync_task(self):
        print('-> Synchronizing...')
        something_changed = False



        if something_changed:
            print('-> Synchronized with Google Drive!')
        else:
            print('-> Nothing changed.')
        # Repeat task
        self.scheduler.enter(delay=self.sync_interval, priority=1, action=self.sync_task)

def main():
    print("=== DriveSync v0.1, by Rafael 'jabyftw' Santos ===")
    drive_sync = DriveSync()

if __name__ == '__main__':
    main()
