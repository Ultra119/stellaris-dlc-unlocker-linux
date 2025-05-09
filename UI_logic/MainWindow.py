import os
from shutil import rmtree, copytree
import stat
from zipfile import ZipFile, BadZipFile
import zipfile
import shutil

import requests
from PyQt5.QtGui import QDesktopServices, QColor, QBrush, QIcon, QClipboard
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QListWidgetItem, QProgressDialog, QApplication
from PyQt5.QtCore import Qt, QUrl, QTimer, QTranslator, pyqtSlot, QThread, QMetaObject
from subprocess import run
from pathlib import Path
import subprocess

import UI.ui_main as ui_main
from Libs.ConnectionCheck import ConnectionCheckThread
from Libs.LauncherReinstall import ReinstallThread
from Libs.logger import Logger
from UI_logic.DialogWindow import dialogUi
from UI_logic.ErrorWindow import errorUi
from Libs.GamePath import stellaris_path, launcher_path
from Libs.ServerData import dlc_data
from Libs.CreamApiMaker import CreamAPI
from Libs.DownloadThread import DownloaderThread
from Libs.MD5Check import MD5

class MainWindow(QMainWindow, ui_main.Ui_MainWindow):
    def __init__(self):
        self.win = False

        super(MainWindow, self).__init__()
        self.translator = QTranslator()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setupUi(self)

        if not self.win:
            self.skip_launcher_reinstall_checbox.setChecked(True)
            self.skip_launcher_reinstall_checbox.setVisible(False)
            self.skip_launcher_reinstall_tooltip.setVisible(False)
            self.full_reinstall_checkbox.setVisible(False)
            self.full_reinstall_tooltip.setVisible(False)
            self.alternative_unloc_checkbox.setVisible(False)
            self.label_2.setVisible(False)

        self.setWindowState(Qt.WindowActive)

        self.error = errorUi()
        self.diag = dialogUi()
        self.game_path = None
        self.not_updated_dlc = []
        self.path_change()

        self.kill_process('dowser')
        self.kill_process('stellaris')

        self.draggable_elements = [self.frame_user, self.server_status, self.gh_status, self.lappname_title,
                                   self.frame_top]
        for element in self.draggable_elements:
            element.mousePressEvent = self.mousePressEvent
            element.mouseMoveEvent = self.mouseMoveEvent
            element.mouseReleaseEvent = self.mouseReleaseEvent

        self.is_dragging = False
        self.last_mouse_position = None
        self.launcher_downloaded = None
        self.continued = False
        self.downloaded_launcher_dir = None
        self.parent_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.is_downloading = False
        self.download_thread = None
        self.creamapidone = False

        self.GITHUB_REPO = "https://api.github.com/repos/seuyh/stellaris-dlc-unlocker/releases/latest"
        self.current_version = '2.21' # This should be managed properly if releases are made
        self.version_label.setText(f'Ver. {str(self.current_version)}')

        self.copy_files_radio.setVisible(False)
        self.download_files_radio.setVisible(False)
        self.launcher_reinstall_radio.setVisible(False)
        self.progress_label.setVisible(False)
        self.dlc_download_label.setVisible(False)
        self.dlc_download_progress_bar.setVisible(False)
        self.current_dlc_label.setVisible(False)
        self.current_dlc_progress_bar.setVisible(False)
        self.lauch_game_checkbox.setVisible(False)
        self.done_button.setVisible(False)

        self.speed_label.setVisible(False)
        self.update_dlc_button.setVisible(False)
        self.old_dlc_text.setVisible(False)
        self.en_lang.toggled.connect(self.switch_to_english)
        self.ru_lang.toggled.connect(self.switch_to_russian)
        self.cn_lang.toggled.connect(self.switch_to_chinese)
        self.connection_thread = ConnectionCheckThread()

        self.connection_thread.github_status_checked.connect(self.handle_github_status)
        self.connection_thread.server_status_checked.connect(self.handle_server_status)

        self.setWindowTitle("Stellaris DLC Unlocker (Linux)")
        self.setWindowIcon(QIcon(os.path.join(self.parent_directory, 'UI', 'icons', 'stellaris.png')))


        self.bn_bug.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(2))
        self.path_choose_button.clicked.connect(self.browse_folder)
        self.next_button.clicked.connect(
            lambda: (
                setattr(self, 'continued', True),
                self.stackedWidget.setCurrentIndex(1),
                self.old_dlc_show()
            )
        )
        self.bn_home.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(1 if self.continued else 0))
        self.unlock_button.clicked.connect(self.unlock)
        self.done_button.clicked.connect(self.finish)

        self.bn_close.clicked.connect(
            lambda: self.close() if self.dialogexec(self.tr("Close"), self.tr("Exit Unlocker?"), self.tr("No"),
                                                    self.tr("Yes")) else None)

        self.bottom_label_github.linkActivated.connect(self.open_link_in_browser)
        self.logger = Logger('unlocker.log')
        self.logger.log_message_signal.connect(self.append_log_message_to_widget)
        self.logger.request_error_dialog_signal.connect(self.show_logger_error_dialog)
        self.log_widget.clear()

    @pyqtSlot(str)
    def append_log_message_to_widget(self, log_text):
        self.log_widget.addItem(log_text)
        self.log_widget.scrollToBottom()

    @pyqtSlot(str, str, str, bool)
    def show_logger_error_dialog(self, heading, btn_ok_text, icon_path, exit_app):
        self.errorexec(heading, btn_ok_text, icon_path, exit_app)

    def showEvent(self, event):
        super(MainWindow, self).showEvent(event)
        print('Start connection check')
        QTimer.singleShot(5, self.start_connection_check)
        print('Start updates check')
        QTimer.singleShot(4, lambda: self.check_for_updates(self.current_version))

    def switch_to_russian(self):
        if self.ru_lang.isChecked():
            if self.translator.load(os.path.join(self.parent_directory, "UI", "translations", "ru_RU.qm")):
                print("ru_RU translate Successfully loaded")
                QApplication.installTranslator(self.translator)
                self.retranslateUi(self)
            else:
                print("Unable to load ru_RU.qm")

    def switch_to_english(self):
        if self.en_lang.isChecked():
            QApplication.removeTranslator(self.translator)
            print("en-US translate Successfully loaded")
            self.retranslateUi(self)

    def switch_to_chinese(self):
        if self.cn_lang.isChecked():
            if self.translator.load(os.path.join(self.parent_directory, "UI", "translations", "zh_CN.qm")):
                print("zh_CN translate Successfully loaded")
                QApplication.installTranslator(self.translator)
                self.retranslateUi(self)
            else:
                print("Unable to load zh_CN.qm")

    @staticmethod
    def open_link_in_browser(url):
        print(f"Attempting to open URL: {url}")
        QDesktopServices.openUrl(QUrl(url))

    def kill_process(self, process_name):
        print(f'Killing {process_name}')
        try:
            run(["pkill", "-f", process_name], check=True)
        except subprocess.CalledProcessError:
            print(f'No process named {process_name} running or pkill error.')
        except FileNotFoundError:
            print(f'pkill command not found. Cannot kill process {process_name}.')


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.last_mouse_position = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.move(event.globalPos() - self.last_mouse_position)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False

    def dialogexec(self, heading, message, btn1, btn2, icon=":/icons/icons/1x/errorAsset 55.png"):
        print(f'Dialog exec: {heading}, {message}, {btn1}, {btn2}, {icon}')
        dialogUi.dialogConstrict(self.diag, heading, message, btn1, btn2, icon, self)
        return self.diag.exec_()

    def errorexec(self, heading, btnOk, icon=":/icons/icons/1x/closeAsset 43.png", exitApp=False):
        print(f'Error exec: {heading}, {btnOk}, {icon}, {exitApp}')
        errorUi.errorConstrict(self.error, heading, icon, btnOk, self, exitApp)
        self.error.exec_()

    def path_change(self):
        path = stellaris_path()
        if path and os.path.isdir(path):
            print(f'Auto detected game path: {path}')
            self.game_path_line.setText(path)
            self.game_path = path
            self.loadDLCNames()
        else:
            print(f'Cant detect game path automatically or path is invalid.')
            self.game_path_line.setText("") 
            self.game_path = None


    def browse_folder(self):
        directory = QFileDialog.getExistingDirectory(self, self.tr("Choose Stellaris path"),
                                                     self.game_path_line.text() or os.path.expanduser("~"))
        if directory:
            if os.path.isfile(os.path.join(directory, "stellaris")):
                self.game_path_line.setText(directory)
                self.game_path = directory
                print(f'Path browsed: {self.game_path}')
                self.loadDLCNames()
            else:
                print('Path browsed incorrectly (stellaris executable not found).')
                self.errorexec(self.tr("This is not Stellaris path (stellaris executable not found)"), self.tr("Ok"))


    def path_check(self):
        path = os.path.normpath(self.game_path_line.text())
        try:
            if os.path.isfile(os.path.join(path, "stellaris")):
                print(f'Game path: {path}')
                return path
        except Exception as e:
            print(f"Error during path check for '{path}': {e}")
            pass
        
        print(f'Path check failed for: {path}')
        self.errorexec(self.tr("Please choose game path (stellaris executable not found)"), self.tr("Ok"))
        return False

    def old_dlc_show(self):
        if self.not_updated_dlc:
            print(f"Not updated DLCs: {self.not_updated_dlc}")
            self.update_dlc_button.setVisible(True)
            self.old_dlc_text.setVisible(True)
        else:
            self.update_dlc_button.setChecked(False)
            self.update_dlc_button.setVisible(False)
            self.old_dlc_text.setVisible(False)
            print("All DLCs are up to date or server return error")


    def check_for_updates(self, current_version):
        try:
            response = requests.get(self.GITHUB_REPO)
            if response.status_code == 200:
                response.raise_for_status()
                latest_release = response.json()
                latest_version = latest_release['tag_name']

                if latest_version != current_version:
                    print(f"Found new version: {latest_version}.")
                    download_url = latest_release.get('html_url')

                    linux_asset_url = None
                    for asset in latest_release.get('assets', []):
                        asset_name_lower = asset.get('name', '').lower()
                        if any(ext in asset_name_lower for ext in ['.appimage', '.tar.gz', '.deb', '.rpm']) and \
                           not any(win_ext in asset_name_lower for win_ext in ['.exe', '.msi']):
                            linux_asset_url = asset.get('browser_download_url')
                            break
                    
                    if not linux_asset_url and latest_release.get('assets'):
                        for asset in latest_release['assets']:
                            asset_name_lower = asset.get('name', '').lower()
                            if not any(win_ext in asset_name_lower for win_ext in ['.exe', '.msi']):
                                linux_asset_url = asset.get('browser_download_url')
                                break
                    
                    final_url_to_open = linux_asset_url or download_url

                    if final_url_to_open and self.dialogexec(self.tr('New version'),
                                       self.tr('New version found ({0}).\nPlease update the program to ensure correct functionality.').format(latest_version),
                                       self.tr('Cancel'), self.tr('Update')):
                        self.open_link_in_browser(final_url_to_open)
                else:
                    print(f"Unlocker is up to date (Version: {current_version})")
            else:
                print(f"Failed to check for updates. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Cant check updates due to network error: {e}")
        except Exception as e:
            print(f"Error during update check: {e}")


    def start_connection_check(self):
        self.connection_thread.start()

    def handle_github_status(self, status):
        if status:
            self.gh_status.setChecked(True)
            print('GitHub connection established')
        else:
            print('GitHub connection cant be established')
            self.errorexec(self.tr("Can't establish connection with GitHub. Check internet"), self.tr("Ok"),
                           exitApp=True)


    def handle_server_status(self, status):
        if status:
            self.server_status.setChecked(True)
            print('Server connection established')
        else:
            print('Server connection cant be established')
            if self.dialogexec(self.tr('Connection error'), self.tr(
                    'Cant establish connection with server\nCheck your connection or you can try download DLC directly\nUnzip downloaded "dlc" folder to game folder\nThen you can continue'),
                               self.tr("Exit"), self.tr("Open")):
                self.open_link_in_browser('https://mega.nz/folder/4zFRnD6a#aVGAK32ZHPxCp7bMtG87BA')
            else:
                self.close()

    def loadDLCNames(self):
        self.dlc_status_widget.clear()
        if not self.game_path or not os.path.isdir(self.game_path):
            print("Game path not set or invalid, cannot load DLC names.")
            item = QListWidgetItem(self.tr("Set game path to see DLC status"))
            item.setForeground(QBrush(QColor("gray")))
            self.dlc_status_widget.addItem(item)
            return

        self.not_updated_dlc = self.checkDLCUpdate()

        for dlc in dlc_data:
            dlc_name = dlc.get('dlc_name', '').strip()
            if not dlc_name:
                continue

            item = QListWidgetItem(dlc_name)

            status_color = self.checkDLCStatus(dlc.get('dlc_folder', ''))

            if status_color != 'black':
                item.setForeground(QBrush(QColor(status_color)))
                if status_color == "orange":
                    item.setText(item.text() + self.tr(" (old/mismatched)"))
                elif status_color == "LightCoral":
                     item.setText(item.text() + self.tr(" (missing)"))
                elif status_color == "teal":
                     item.setText(item.text() + self.tr(" (OK)"))
                self.dlc_status_widget.addItem(item)

    def checkDLCStatus(self, dlc_folder):
        if not dlc_folder:
            return "black"
        
        if not self.game_path:
            return "LightCoral"

        dlc_path_folder = os.path.join(self.game_path, "dlc", dlc_folder)
        dlc_path_zip = os.path.join(self.game_path, "dlc", f'{dlc_folder}.zip')
        
        is_present_as_folder = os.path.exists(dlc_path_folder)
        is_present_as_zip = os.path.exists(dlc_path_zip)

        if is_present_as_folder or (is_present_as_zip and not self.is_invalid_zip(dlc_path_zip)):
            if dlc_folder in self.not_updated_dlc:
                return "orange"
            return "teal"
        else:
            return "LightCoral"


    def checkDLCUpdate(self):
        if not self.game_path or not os.path.isdir(os.path.join(self.game_path, "dlc")):
            print("DLC directory not found for MD5 check.")
            return []
        
        md5_checker = MD5(os.path.join(self.game_path, "dlc"), "stlunlocker.pro")
        return md5_checker.check_files()

    @staticmethod
    def full_reinstall():
        print(f'Full reinstall: Skipped (Windows-specific user data path removal).')
        pass

    def download_alt_method(self):
        print('Alternative (MSI) launcher download: Skipped (Windows-specific).')
        self.launcher_downloaded = False
        return

    def unlock(self):
        print('Unlocking...')
        if not self.path_check():
            print('Error: incorrect game path, aborting unlock.')
            return
        
        self.game_path = os.path.normpath(self.game_path_line.text())
        print('Unlock started for Linux')
        print(
            f'Settings:\nPath: {self.game_path}\n'
            f'Skip launcher reinstall: {self.skip_launcher_reinstall_checbox.isChecked()} (Effectively True on Linux)'
        )

        self.unlock_button.setEnabled(False)
        self.game_path_line.setEnabled(False)
        self.path_choose_button.setEnabled(False)
        self.full_reinstall_checkbox.setEnabled(False)
        self.alternative_unloc_checkbox.setEnabled(False)
        self.skip_launcher_reinstall_checbox.setEnabled(False)
        self.update_dlc_button.setEnabled(False)
        self.copy_files_radio.setVisible(True)
        self.download_files_radio.setVisible(True)
        self.launcher_reinstall_radio.setVisible(True)
        self.progress_label.setVisible(True)
        self.dlc_download_label.setVisible(True)
        self.dlc_download_progress_bar.setVisible(True)
        self.current_dlc_label.setVisible(True)
        self.current_dlc_progress_bar.setVisible(True)
        self.speed_label.setVisible(True)

        dlc_base_path = os.path.join(self.game_path, "dlc")
        if not os.path.exists(dlc_base_path):
            try:
                os.makedirs(dlc_base_path)
                print(f"Created DLC directory: {dlc_base_path}")
            except OSError as e:
                print(f"Failed to create DLC directory {dlc_base_path}: {e}")
                self.errorexec(self.tr("Failed to create DLC directory."), self.tr("Ok"), exitApp=True)
                return


        if self.game_path:
            self.is_downloading = True
            if self.update_dlc_button.isChecked() and self.update_dlc_button.isVisible():
                print("Updating (redownloading) mismatched/old DLCs...")
                self.delete_folders(os.path.join(self.game_path, "dlc"), self.not_updated_dlc)
                self.not_updated_dlc = []
            self.loadDLCNames()
            self.creamapi_maker = CreamAPI()
            self.creamapi_maker.progress_signal.connect(self.update_creamapi_progress)
            self.creamapi_maker.start()
            self.dlc_count = 0
            self.dlc_downloaded = 0
            self.download_queue = []

            def start_next_download():
                if self.download_queue:
                    file_url, save_path = self.download_queue.pop(0)
                    self.download_thread = DownloaderThread(file_url, save_path, self.dlc_downloaded, self.dlc_count)
                    self.download_thread.progress_signal.connect(self.update_progress)
                    self.download_thread.progress_signal_2.connect(self.update_progress_2)
                    self.download_thread.error_signal.connect(self.show_error)
                    self.download_thread.speed_signal.connect(self.show_download_speed)
                    self.download_thread.finished.connect(start_next_download)
                    self.download_thread.start()
                elif self.dlc_downloaded == self.dlc_count :
                    self.update_progress(100)

            for item in dlc_data:
                if 'dlc_folder' in item and item['dlc_folder']:
                    self.dlc_count += 1
            
            if self.dlc_count == 0:
                print("No DLCs with specified folders found in configuration. Skipping downloads.")
                self.update_progress(100)
                return

            for dlc in dlc_data:
                dlc_folder_name = dlc.get('dlc_folder')
                if not dlc_folder_name:
                    continue

                file_url = f"{'https://stlunlocker.pro/unlocker/'}{dlc_folder_name}.zip"
                save_path_zip = os.path.join(self.game_path, 'dlc', f'{dlc_folder_name}.zip')
                extracted_folder_path = os.path.join(self.game_path, 'dlc', dlc_folder_name)

                if not os.path.exists(extracted_folder_path) and self.is_invalid_zip(save_path_zip):
                    if os.path.exists(save_path_zip):
                        try:
                            os.remove(save_path_zip)
                            print(f"Removed invalid/incomplete zip: {save_path_zip}")
                        except OSError as e:
                             print(f"Error removing invalid zip {save_path_zip}: {e}")
                    self.download_queue.append((file_url, save_path_zip))
                else:
                    self.dlc_downloaded += 1
                    current_progress = int((self.dlc_downloaded / self.dlc_count) * 100) if self.dlc_count > 0 else 0
                    self.update_progress(current_progress)


            if self.download_queue:
                print(f'Starting downloads for {len(self.download_queue)} DLCs...')
                if self.server_status.isChecked():
                    start_next_download()
                else:
                    self.errorexec(self.tr("Cannot download DLCs: Server connection failed."), self.tr("Ok"))
                    self.download_files_radio.setVisible(False)
                    self.unlock_button.setEnabled(True)
                    return
            elif self.dlc_downloaded == self.dlc_count and self.dlc_count > 0:
                print("All DLCs already present. Proceeding to next step.")
                self.update_progress(100)
            elif self.dlc_count == 0 :
                 print("No DLCs to download. Proceeding to next step.")
                 self.update_progress(100)


    def update_creamapi_progress(self, value):
        if value == 100:
            self.creamapidone = True
            print("CreamAPI generation complete.")
            self.download_complete()

    @staticmethod
    def is_invalid_zip(path):
        if not os.path.exists(path):
            return True
        if os.path.getsize(path) == 0:
            return True
        try:
            with ZipFile(path, 'r') as zf:
                if zf.testzip() is not None:
                    return True
        except BadZipFile:
            return True
        return False

    @staticmethod
    def delete_folders(base_path, folders_to_delete):
        base_path_obj = Path(base_path)

        for folder_name in folders_to_delete:
            dir_path_to_delete = base_path_obj / folder_name
            zip_path_to_delete = base_path_obj / f"{folder_name}.zip"
            try:
                if dir_path_to_delete.is_dir():
                    rmtree(dir_path_to_delete)
                    print(f"Deleted directory: {dir_path_to_delete}")
                if zip_path_to_delete.is_file():
                    os.remove(zip_path_to_delete)
                    print(f"Deleted zip file: {zip_path_to_delete}")
            except Exception as e:
                print(f"Can't delete {folder_name} (dir/zip): {e}")


    def update_progress(self, value, by_download=False):
        self.dlc_download_progress_bar.setValue(value)
        if by_download:
            self.dlc_downloaded += 1
            current_progress = int((self.dlc_downloaded / self.dlc_count) * 100) if self.dlc_count > 0 else 0
            self.dlc_download_progress_bar.setValue(current_progress)
            self.loadDLCNames()
        
        if self.dlc_download_progress_bar.value() == 100:
            self.speed_label.setText("")
            self.update_progress_2(100)
            self.download_complete()


    def update_progress_2(self, value):
        self.current_dlc_progress_bar.setValue(value)

    def show_download_speed(self, speed):
        self.speed_label.setText(f'{speed:.1f} MB/s')

    def show_error(self, error_message):
        print(f'DownloadThread error signal: {error_message}')
        self.errorexec(self.tr("File download error: {0}").format(str(error_message)), self.tr("Exit"), exitApp=True)


    def show_reinstall_error(self, error_message):
        print(f'ReinstallThread (Linux stub) error signal: {error_message}')

    def download_complete(self):
        if QThread.currentThread() != self.thread():
            print("Warning: download_complete called off-thread, re-queuing.")
            QTimer.singleShot(0, self.download_complete)
            return

        if self.dlc_download_progress_bar.value() == 100 and self.creamapidone:
            print('All DLC downloads and CreamAPI generation complete.')
            self.download_files_radio.setChecked(True)
            self.reinstall()


    def reinstall(self):
        print('Setting up CreamLinux...')
        print('Skipping Windows-style launcher reinstall, proceeding with CreamLinux setup flow.')
        self.reinstall_2(self.game_path)


    def reinstall_2(self, launcher_install_dir_or_game_path_linux):
        self.replace_files_linux()
        return

    def replace_files_linux(self):
        self.launcher_reinstall_radio.setChecked(True)
        print(f'Preparing CreamLinux files for game path: {self.game_path}')

        try:
            print('Unzipping downloaded DLCs...')
            dlc_dir = os.path.join(self.game_path, 'dlc')
            zip_files = [f for f in os.listdir(dlc_dir) if f.endswith('.zip') and os.path.isfile(os.path.join(dlc_dir, f))]
            if zip_files:
                for zip_file_name in zip_files:
                    full_zip_path = os.path.join(dlc_dir, zip_file_name)
                    if not self.is_invalid_zip(full_zip_path):
                        self.unzip_and_replace(zip_file_name)
                    else:
                        print(f"Skipping unzip for invalid/empty zip: {zip_file_name}")
            else:
                print("No new .zip files found to unzip in DLC directory.")
        except Exception as e:
            print(f"Error during DLC unzipping process: {e}")
            self.errorexec(self.tr("Error while unzipping DLCs: {0}").format(str(e)), self.tr("Exit"), exitApp=True)
            return

        try:
            if self.install_creamlinux(281990, self.game_path, dlc_data):
                self.copy_files_radio.setChecked(True)
                
                launch_option_text = 'sh ./cream.sh %command%'
                if self.dialogexec(self.tr('Game Unlocked with CreamLinux!'),
                                   self.tr('The game is unlocked!\n'
                                           'Please manually add the following to the game\'s launch options in Steam:\n\n'
                                           '{0}\n\n'
                                           'Click "Copy" to copy this text to your clipboard.').format(launch_option_text),
                                   self.tr('Close'), self.tr('Copy')):
                    QApplication.clipboard().setText(launch_option_text)
                    self.errorexec(self.tr("Launch option copied to clipboard!"), self.tr("Ok"))


                print('CreamLinux setup complete.')
                self.lauch_game_checkbox.setVisible(True)
                self.done_button.setVisible(True)
                print('All unlocking steps done for Linux!')
            else:
                self.errorexec(self.tr("CreamLinux setup failed."), self.tr("Exit"), exitApp=True)
        except Exception as e:
            print(f"Error during CreamLinux installation: {e}")
            self.errorexec(self.tr("CreamLinux setup error: {0}").format(str(e)), self.tr("Exit"), exitApp=True)


    def install_creamlinux(self, app_id, game_install_dir, dlc_list_from_data_file):
        print(f"Installing CreamLinux for app_id {app_id} in {game_install_dir}")
        source_cream_linux_files_dir = os.path.join(self.parent_directory, 'creamlinux')
        if not os.path.isdir(source_cream_linux_files_dir):
             source_cream_linux_files_dir = os.path.join(self.parent_directory, 'creamlinux')
             if not os.path.isdir(source_cream_linux_files_dir):
                raise FileNotFoundError(f"CreamLinux source files directory not found at expected locations: "
                                    f"{os.path.join(self.parent_directory, 'creamlinux')} or "
                                    f"{os.path.join(self.parent_directory, 'creamlinux')}")

        specific_ini_source_dir = os.path.join(self.parent_directory, 'creamlinux')
        source_ini_path = os.path.join(specific_ini_source_dir, 'cream_api.ini')

        if not os.path.isfile(source_ini_path):
            raise FileNotFoundError(f"Generated cream_api.ini not found at {source_ini_path}. CreamApiMaker might have failed.")

        try:
            if os.path.isdir(os.path.join(self.parent_directory, 'creamlinux')):
                copytree(os.path.join(self.parent_directory, 'creamlinux'), game_install_dir, dirs_exist_ok=True)
                print(f"Copied base CreamLinux files from 'creamlinux' to {game_install_dir}")
            else:
                copytree(specific_ini_source_dir, game_install_dir, dirs_exist_ok=True)
                print(f"Copied base CreamLinux files from 'creamlinux' to {game_install_dir} (linux subdir missing)")

            target_ini_path = os.path.join(game_install_dir, 'cream_api.ini')
            shutil.copy2(source_ini_path, target_ini_path)
            print(f"Copied generated cream_api.ini to {target_ini_path}")

        except Exception as e:
            raise Exception(f"Failed to copy CreamLinux files to game directory: {str(e)}")

        cream_sh_path = os.path.join(game_install_dir, "cream.sh")
        if os.path.isfile(cream_sh_path):
            try:
                current_permissions = os.stat(cream_sh_path).st_mode
                os.chmod(cream_sh_path, current_permissions | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
                print(f"Set execute permissions for {cream_sh_path}")
            except OSError as e:
                raise Exception(f"Failed to set execute permissions for {cream_sh_path}: {str(e)}")
        else:
            raise FileNotFoundError(f"cream.sh not found at {cream_sh_path} after copy operation.")

        return True


    def unzip_and_replace(self, dlc_zip_filename):
        zip_path = os.path.join(self.game_path, 'dlc', dlc_zip_filename)
        extract_folder = os.path.join(self.game_path, 'dlc')
        if not os.path.exists(extract_folder):
            os.makedirs(extract_folder)

        print(f"Unzipping: {zip_path} into {extract_folder}")
        try:
            with ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
            os.remove(zip_path)
            print(f"Successfully unzipped and removed {zip_path}")
            return extract_folder
        except Exception as e:
            print(f'Error while unzipping {dlc_zip_filename}: {e}')
            raise


    def finish(self):
        if self.lauch_game_checkbox.isChecked():
            try:
                print("Attempting to launch Stellaris via Steam (xdg-open)...")
                run(['xdg-open', 'steam://run/281990'], check=True)
            except FileNotFoundError:
                print("xdg-open command not found. Cannot launch game via Steam automatically.")
                self.errorexec(self.tr("xdg-open not found. Cannot launch game."), self.tr("Ok"))
            except subprocess.CalledProcessError as e:
                print(f"Error launching game via Steam: {e}")
                self.errorexec(self.tr("Failed to launch game via Steam: {0}").format(str(e)), self.tr("Ok"))
            except Exception as e:
                print(f"An unexpected error occurred while trying to launch game: {e}")
                self.errorexec(self.tr("Unexpected error launching game: {0}").format(str(e)), self.tr("Ok"))
        self.close()
