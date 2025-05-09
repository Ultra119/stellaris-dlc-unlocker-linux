from requests import get
from time import sleep
from PyQt5 import QtCore
import os


class CreamAPI(QtCore.QThread):
    progress_signal = QtCore.pyqtSignal(int)

    def __init__(self):
        super().__init__()
        # self.dlc_callback = dlc_callback
        # self.progress_callback = progress_callback
        self.parent_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def get_dlc_name(self, dlc_id, errors=0):
        print('CreamApi creating... (get_dlc_name)')
        url = f"https://api.steamcmd.net/v1/info/{dlc_id}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Host": "api.steamcmd.net",
            "Upgrade-Insecure-Requests": "1"
        }
        try:
            response = get(url, headers=headers, timeout=3)
            print(f"Response for DLC ID {dlc_id}: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                dlc_name = data['data'][str(dlc_id)]['common']['name']
                print(f"DLC Name for {dlc_id}: {dlc_name}")
                return dlc_name
            else:
                print(f"Failed to get DLC name for {dlc_id}, status code: {response.status_code}")
                if errors >= 3:
                    return None
                errors += 1
                print('Retrying get_dlc_name...')
                return self.get_dlc_name(dlc_id, errors)

        except Exception as e:
            print(f"Exception in get_dlc_name for {dlc_id}: {e}")
            if errors >= 3:
                return False
            errors += 1
            print('Cant connect steamcmd (exception). Retrying get_dlc_name...')
            return self.get_dlc_name(dlc_id, errors)

    def get_dlc_list(self, app_id, errors=0):
        print('CreamApi creating... (get_dlc_list)')
        url = f"https://api.steamcmd.net/v1/info/{app_id}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Host": "api.steamcmd.net",
            "Upgrade-Insecure-Requests": "1"
        }
        try:
            response = get(url, headers=headers, timeout=3)
            print(f"Response for App ID {app_id} (DLC list): {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                app_data = data.get('data', {}).get(str(app_id), {})
                extended_data = app_data.get('extended', {})
                dlc_list_json = extended_data.get('listofdlc')

                if dlc_list_json is None:
                    print(f"'listofdlc' not found for app_id {app_id} in response.")
                    if errors >= 3:
                        return False
                    errors += 1
                    print('Retrying get_dlc_list (listofdlc not found)...')
                    return self.get_dlc_list(app_id, errors)
                
                dlc_list = dlc_list_json.split(',')
                return dlc_list
            else:
                print(f"Failed to get DLC list for {app_id}, status code: {response.status_code}")
                if errors >= 3:
                    return False
                errors += 1
                print('Retrying get_dlc_list (non-200 status)...')
                return self.get_dlc_list(app_id, errors)

        except Exception as e:
            print(f"Exception in get_dlc_list for {app_id}: {e}")
            if errors >= 3:
                return False
            errors += 1
            print('Cant connect steamcmd (exception). Retrying get_dlc_list...')
            return self.get_dlc_list(app_id, errors)

    def run(self):
        print('Cream api creating process starting...')
        dlc_list = self.get_dlc_list(281990)
        print(f"Retrieved DLC list: {dlc_list}")
        if dlc_list:
            if dlc_list is False:
                print('Failed to retrieve DLC list from SteamCMD API. Skipped cream_api.ini update.')
            else:
                game_cream_api_path = os.path.join(self.parent_directory, 'creamlinux', 'cream_api.ini')
                os.makedirs(os.path.dirname(game_cream_api_path), exist_ok=True)

                self.check_and_update_dlc_list(dlc_list, game_cream_api_path)

            self.progress_signal.emit(100)
        else:
            print('SteamCmd API unavailable or no DLCs found. Skipped cream_api.ini update.')
            self.progress_signal.emit(100)
            return


    def check_and_update_dlc_list(self, dlc_list, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        existing_content = ""
        try:
            with open(path, 'r') as file:
                existing_content = file.read()
        except FileNotFoundError:
            print(f"cream_api.ini not found at {path}, will create a new one.")
        except Exception as e:
            print(f"Error reading {path}: {e}. Proceeding to write/overwrite.")
        
        new_dlcs_added_count = 0
        dlc_lines_to_add = []

        for dlc_id in dlc_list:
            if not dlc_id.strip():
                continue
            if f"\n{dlc_id} =" not in existing_content and f"{dlc_id} =" not in existing_content:
                dlc_name = self.get_dlc_name(dlc_id)
                if dlc_name:
                    dlc_lines_to_add.append(f"{dlc_id} = {dlc_name}")
                    new_dlcs_added_count +=1
                elif dlc_name is None:
                    print(f"Could not retrieve name for DLC ID {dlc_id} after retries. Skipping.")
        
        if dlc_lines_to_add:
            try:
                with open(path, 'a+') as file:
                    file.seek(0, 2)
                    if existing_content and not existing_content.endswith('\n'):
                        file.write('\n')
                    for line in dlc_lines_to_add:
                        file.write(f"{line}\n")
                print(f'{new_dlcs_added_count} new DLC(s) written to {path}')
            except Exception as e:
                print(f"Error writing to {path}: {e}")
        else:
            print(f'No new DLCs to add to {path}.')
