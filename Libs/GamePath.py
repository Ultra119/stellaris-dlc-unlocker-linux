import os.path
from vdf import loads


def get_steam_path():
    return os.path.expanduser("~/.steam/steam")


def stellaris_path():
    try:
        steam_path_val = get_steam_path()
        if not steam_path_val or not os.path.isdir(steam_path_val):
            print(f"Steam path not found or invalid: {steam_path_val}")
            return 0

        vdf_file_path = os.path.join(steam_path_val, "steamapps", "libraryfolders.vdf")
        if not os.path.isfile(vdf_file_path):
            flatpak_vdf_path = os.path.expanduser("~/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/libraryfolders.vdf")
            if os.path.isfile(flatpak_vdf_path):
                vdf_file_path = flatpak_vdf_path
            else:
                steam_apps_path = os.path.join(steam_path_val, "steamapps")
                if os.path.isdir(steam_apps_path):
                    potential_library_folders_vdf = [
                        os.path.join(root, "libraryfolders.vdf")
                        for root, dirs, files in os.walk(os.path.expanduser("~/.steam/"))
                        if "libraryfolders.vdf" in files and "steamapps" in root
                    ]
                    if not potential_library_folders_vdf:
                         potential_library_folders_vdf = [
                            os.path.join(root, "libraryfolders.vdf")
                            for root, dirs, files in os.walk(os.path.expanduser("~/.local/share/Steam/"))
                            if "libraryfolders.vdf" in files and "steamapps" in root
                        ]

                    if potential_library_folders_vdf:
                        vdf_file_path = min(potential_library_folders_vdf, key=len)
                        print(f"Found libraryfolders.vdf at: {vdf_file_path}")
                    else:
                        print(f"libraryfolders.vdf not found in standard or Flatpak Steam paths or common library locations.")
                        return 0

        with open(vdf_file_path, 'r', encoding='utf-8') as vdf_file:
            vdf_data = loads(vdf_file.read())

        if "libraryfolders" in vdf_data:
            libraryfolders = vdf_data["libraryfolders"]
            for key, value in libraryfolders.items():
                if isinstance(value, dict) and "path" in value and "apps" in value and "281990" in value["apps"]:
                    base_library_path = value["path"]
                    if not os.path.isabs(base_library_path):
                        print(f"Warning: Path in libraryfolders.vdf is not absolute: {base_library_path}")
                        continue
                    
                    game_path = os.path.join(base_library_path, "steamapps", "common", "Stellaris")
                    if os.path.isdir(game_path):
                        return game_path
            else:
                print("Stellaris (AppID 281990) not found in any Steam library.")
                return 0
        else:
            print("'libraryfolders' key not found in VDF data.")
            return 0
    except FileNotFoundError:
        print(f"Steam VDF file not found at expected locations.")
        return 0
    except Exception as e:
        print(f"Error reading Steam library configuration: {e}")
        return 0


def launcher_path():
    user_home = os.path.expanduser("~")
    launcher_path_1 = os.path.join(user_home, ".paradoxlauncher")
    launcher_path_2 = os.path.join(user_home, ".config", "Paradox Interactive", "launcher-v2")
    launcher_path_3 = os.path.join(user_home, ".local", "share", "Paradox Interactive", "launcher-v2")
    launcher_path_4 = os.path.join(user_home, ".local", "share", "Paradox Interactive")

    return (
        launcher_path_1 if os.path.isdir(launcher_path_1) else "",
        launcher_path_2 if os.path.isdir(launcher_path_2) else "",
        launcher_path_3 if os.path.isdir(launcher_path_3) else "",
        launcher_path_4 if os.path.isdir(launcher_path_4) else ""
    )
