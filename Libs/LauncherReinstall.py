import os
from shutil import rmtree, move
from PyQt5 import QtCore


class ReinstallThread(QtCore.QThread):
    error_signal = QtCore.pyqtSignal(Exception)
    continue_reinstall = QtCore.pyqtSignal(str)

    def __init__(self, msi_path, paradox_folder1, paradox_folder2, paradox_folder3, paradox_folder4,
                 launcher_downloaded, downloaded_launcher_dir):
        super().__init__()
        self.msi_path = msi_path
        self.paradox_folder1 = paradox_folder1

    def run(self):
        print("LauncherReinstallThread: Skipping Windows-specific launcher reinstallation.")
        self.continue_reinstall.emit(self.paradox_folder1)


    @staticmethod
    def paradox_remove(paradox_folder1, paradox_folder2, paradox_folder3, paradox_folder4):
        print("LauncherReinstallThread.paradox_remove: Skipping Windows-specific folder removal.")
        pass
