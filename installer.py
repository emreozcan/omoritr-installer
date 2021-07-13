import json
import logging
import os.path
import shutil
import sys
import tkinter
import traceback
import winreg
import zipfile
from glob import glob
from pathlib import Path


def get_steam_path() -> Path:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "SOFTWARE\\Valve\\Steam") as key:
        return Path(winreg.QueryValueEx(key, "SteamPath")[0])


def get_game_dir(steampath: Path) -> Path or None:
    default_path = steampath / "steamapps/common/OMORI"
    if (default_path / "OMORI.exe").exists():
        return default_path

    library_map_file = steampath / "steamapps/libraryfolders.vdf"
    if not library_map_file.exists():
        return None
    logging.warning(f"Collecting strings from {library_map_file = }")
    strings = library_map_file.read_text("utf-8").split("\"")
    logging.debug(f"Collected {len(strings) = } strings.")
    for string in strings:
        candidate_path = Path(string)
        logging.debug(f"Checking library candidate {candidate_path = }")
        if not candidate_path.exists():
            logging.debug(" -> Path doesn't exist.")
            continue
        logging.debug(" -> Path exists.")
        candidate_exec_path = candidate_path / "steamapps/common/OMORI/OMORI.exe"
        if candidate_exec_path.exists():
            logging.debug(" -> It has OMORI.")
            game_dir = candidate_exec_path.parent
            logging.info(f"Game found at {game_dir = }")
            return game_dir
        logging.debug(" -> It doesn't have OMORI.")
    logging.error("No string contained a library path that had OMORI in it.")
    logging.error("".join(["Listing all strings:\n", "\n".join(strings)]))
    return None


def is_gomori_installed(gamepath: Path) -> bool:
    return (gamepath / "www/gomori/gomori.js").exists()


def is_plutofix_installed(gamepath: Path) -> bool:
    return "data_pluto" in \
           (gamepath / "www/gomori/constants/filetypes.js").read_text(encoding="utf-8")


def are_translations_installed(gamepath: Path) -> bool:
    return (gamepath / "www/mods/omoritr/mod.json").exists()


def get_translation_version(gamepath: Path) -> str:
    return json.loads(
        (gamepath / "www/mods/omoritr/mod.json").read_text(encoding="utf-8")
    )["version"]


def install_gomori(gomori_archive_path: Path, game_dir: Path) -> None:
    gomori_archive = zipfile.ZipFile(gomori_archive_path, "r", zipfile.ZIP_LZMA)
    gomori_archive.extractall(game_dir)


def install_translations(translation_archive_path: Path, game_dir: Path) -> None:
    translation_archive = zipfile.ZipFile(translation_archive_path, "r", zipfile.ZIP_LZMA)
    translation_archive.extractall(game_dir.joinpath("www/mods/"))


def get_packed_tl_version(translation_archive_path: Path) -> str:
    translation_archive = zipfile.ZipFile(translation_archive_path, "r", zipfile.ZIP_LZMA)
    packed_mod_manifest = translation_archive.read("omoritr/mod.json")
    return json.loads(packed_mod_manifest)["version"]


def safe_delete(container: Path or str, paths: list[Path or str]) -> None:
    logging.warning("Collecting information for delete operation")
    real_container_path = os.path.realpath(container)
    logging.debug(f"{container = }")
    logging.warning(f"{real_container_path = }")
    for target_path in paths:
        logging.warning(f" -- Collecting information about {target_path = }")
        real_target_path = os.path.realpath(target_path)
        logging.debug(f"{target_path = }")
        logging.warning(f"{real_target_path = }")
        if not os.path.exists(real_target_path):
            logging.error("This file does not exist. Why?")
            continue
        if not real_target_path.startswith(real_container_path):
            logging.error("This file is not inside the container. Why?")
            continue
        if os.path.isdir(real_target_path):
            logging.debug("Path is a directory. Performing recursive directory deleting operation.")
            shutil.rmtree(real_target_path)
        else:
            logging.debug("Path is not a directory. Performing unlinking operation.")
            os.unlink(real_target_path)


def clear_gomori(game_dir: Path) -> None:
    names = ["www/JSON-Patch*", "www/adm-zip*", "www/gomori", "www/index.html"]
    gomori_dirs = []
    for name in names:
        glob_path = str(game_dir / name)
        logging.debug(f"{glob_path = }")
        glob_result = glob(glob_path)
        logging.debug(f"{glob_result = }")
        gomori_dirs.extend(glob_result)
    logging.debug(f"{gomori_dirs = }")
    safe_delete(game_dir, gomori_dirs)


def clear_tl(game_dir: Path) -> None:
    tl_path = game_dir / "www/mods/omoritr"
    logging.debug(f"{tl_path = }")
    if tl_path.exists():
        safe_delete(game_dir, [tl_path])


def main():
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        level=logging.DEBUG,
        filename="omoritr-installer.log"
    )

    logging.info("Starting omoritr-installer")
    logging.info("OMORI Türkçe Çeviri Ekibi, 2021")
    logging.info("https://omori-turkce.com")
    logging.info("Installer Emre Özcan github.com/emreozcan")

    bundle_dir = Path(__file__).parent
    logging.debug(f"{bundle_dir = }")
    gomori_archive_path = Path.cwd() / bundle_dir / "res/gomori.zip"
    logging.debug(f"{gomori_archive_path = }")
    translation_archive_path = Path.cwd() / bundle_dir / "res/omoritr.zip"
    logging.debug(f"{translation_archive_path = }")
    icon_path = Path.cwd() / bundle_dir / "res/transparent-256.ico"
    logging.debug(f"{icon_path = }")

    root = tkinter.Tk()
    root.title("OMORI Türkçe Yama yükleyicisi")
    root.iconbitmap(icon_path)
    root.resizable(False, False)

    tkinter.Label(root, text="OMORI Türkçe Yama yükleyicisine hoş geldiniz.", justify="left", anchor="w") \
        .pack(fill="x", padx=5, pady=5)

    steam_dir = None
    try:
        steam_dir = get_steam_path()
    except FileNotFoundError:
        logging.warning("Steam not found.")
        pass

    logging.debug(f"{steam_dir = }")

    game_dir = get_game_dir(steampath=steam_dir)
    logging.debug(f"{game_dir = }")

    omori_installed = game_dir is not None
    logging.debug(f"{omori_installed = }")

    steam_info_label = tkinter.Label(root, justify="left", anchor="w")
    steam_info_label.pack(fill="x", padx=5, pady=5)
    if not omori_installed:
        steam_info_label.config(
            text="Bilgisayarınızda OMORI tespit edilememiştir.\n"
                 "Lütfen bilgisayarınıza OMORI yükleyip bu programı tekrar çalıştırın.",
            fg="#FF0000"
        )
        root.mainloop()
        sys.exit(1)

    gomori_installed = is_gomori_installed(gamepath=game_dir)
    logging.debug(f"{gomori_installed = }")
    plutofix_installed = is_plutofix_installed(gamepath=game_dir) if gomori_installed else False
    logging.debug(f"{plutofix_installed = }")
    gomori_install_required = not gomori_installed or not plutofix_installed
    logging.debug(f"{gomori_install_required = }")

    tl_installed = are_translations_installed(gamepath=game_dir)
    logging.debug(f"{tl_installed = }")
    tl_version = get_translation_version(gamepath=game_dir) if tl_installed else None
    logging.debug(f"(installed) {tl_version = }")

    packed_tl_version = get_packed_tl_version(translation_archive_path)
    logging.debug(f"{packed_tl_version = }")

    steam_info_label.config(
        text="OMORI bilgisayarınızda otomatik olarak tespit edilmiştir.\n"
             "Bilgileri inceleyip düğmeye tıklayarak yamayı yükleyebilirsiniz."
    )

    tkinter.Label(root, text="Oyun konumu:", justify="left", anchor="w") \
        .pack(fill="x", padx=5, pady=(5, 0))

    game_location_entry = tkinter.Entry(root, justify="left")
    game_location_entry.pack(fill="x", padx=5, pady=(0, 5))
    game_location_entry.insert(0, os.path.realpath(game_dir))
    game_location_entry.config(state="disabled")

    tkinter.Label(root, text="Yapılan kontroller:", justify="left", anchor="w") \
        .pack(fill="x", padx=5, pady=(5, 0))

    game_installed_checkbox = tkinter.Checkbutton(root, text="OMORI yüklenmiş", state="disabled", anchor="w")
    if omori_installed:
        game_installed_checkbox.select()
    game_installed_checkbox.pack(fill="x", padx=5, pady=0)

    gomori_installed_checkbox = tkinter.Checkbutton(root, text="GOMORI yüklenmiş", state="disabled", anchor="w")
    if gomori_installed:
        gomori_installed_checkbox.select()
    gomori_installed_checkbox.pack(fill="x", padx=5, pady=0)

    plutofix_installed_checkbox = tkinter.Checkbutton(
        root,
        text="GOMORI için \"data_pluto fix\" yapılmış",
        state="disabled",
        anchor="w"
    )
    if plutofix_installed:
        plutofix_installed_checkbox.select()
    plutofix_installed_checkbox.pack(fill="x", padx=5, pady=0)

    tl_installed_checkbox = tkinter.Checkbutton(root, text="Türkçe Yama yüklenmiş", state="disabled", anchor="w")
    if tl_installed:
        tl_installed_checkbox.select()
        tl_installed_checkbox.config(
            text=f"Türkçe Yama yüklenmiş ({tl_version})"
        )
    tl_installed_checkbox.pack(fill="x", padx=5, pady=(0, 5))

    tkinter.Label(root, text="Yapılması gereken işlemler:", justify="left", anchor="w") \
        .pack(fill="x", padx=5, pady=(5, 0))

    to_install_gomori_checkbox = tkinter.Checkbutton(root, text="GOMORI yüklenecek", state="disabled", anchor="w")
    if gomori_install_required:
        to_install_gomori_checkbox.select()
    if gomori_installed and not plutofix_installed:
        to_install_gomori_checkbox.config(
            text="GOMORI \"data_pluto fix\" için değiştirilecek."
        )
    to_install_gomori_checkbox.pack(fill="x", padx=5)

    to_install_tl_checkbox = tkinter.Checkbutton(root, state="disabled", anchor="w")
    if tl_installed:
        to_install_tl_checkbox.config(
            text=f"Türkçe Yama değiştirilecek (yeni: {packed_tl_version})"
        )
    else:
        to_install_tl_checkbox.config(
            text=f"Türkçe Yama yüklenecek ({packed_tl_version})"
        )
    to_install_tl_checkbox.select()
    to_install_tl_checkbox.pack(fill="x", padx=5, pady=(0, 5))

    def apply_button_callback():
        action_button.config(state="disabled")
        try:
            logging.info("Applying operations")
            if gomori_install_required:
                if gomori_installed:
                    logging.info("Trying to remove old GOMORI installation")
                    clear_gomori(game_dir=game_dir)
                    logging.info("Removed old GOMORI installation.")
                logging.info("Trying to install GOMORI")
                install_gomori(gomori_archive_path=gomori_archive_path, game_dir=game_dir)
                logging.info("Installed GOMORI.")
            if tl_installed:
                logging.info(f"Trying to remove old translation patch ({tl_version = })")
                clear_tl(game_dir=game_dir)
                logging.info("Removed old translation patch.")
            logging.info(f"Installing translation patch ({packed_tl_version = })")
            install_translations(translation_archive_path=translation_archive_path, game_dir=game_dir)
            logging.info("Installed translation patch.")
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            formatted_exception = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            logging.error(formatted_exception)

            alert = tkinter.Toplevel(root)
            alert.title("OMORI Türkçe Yama yükleyicisi")
            alert.iconbitmap(icon_path)
            alert.resizable(False, False)

            tkinter.Label(alert, text="OMORI Türkçe Yama yükleme işlemi sırasında beklenmeyen bir hata oluştu.") \
                .pack(fill="x", padx=5, pady=5)

            stacktrace_widget = tkinter.Text(alert, width=100, height=20)
            stacktrace_widget.insert("1.0", formatted_exception)
            stacktrace_widget.pack(fill="x", padx=5, pady=5)
        else:
            alert = tkinter.Toplevel(root)
            alert.title("OMORI Türkçe Yama yükleyicisi")
            alert.iconbitmap(icon_path)
            alert.resizable(False, False)

            tkinter.Label(alert, text="OMORI Türkçe Yama yükleme işlemi hatasızca tamamlanmıştır.") \
                .pack(fill="x", padx=15, pady=(15, 5))

            tkinter.Button(alert, text="Tamam", command=sys.exit) \
                .pack(ipadx=15, padx=15, pady=(5, 15))

    action_button = tkinter.Button(root, text="Uygula", command=apply_button_callback)
    action_button.pack(pady=5, ipadx=15)

    credit_frame = tkinter.Frame(root)

    tkinter.Label(credit_frame, text="https://omori-turkce.com").pack(fill="x", side="left")
    tkinter.Label(credit_frame, text="OMORI Türkçe Çeviri Ekibi").pack(fill="x", side="right")

    credit_frame.pack(fill="x", side="bottom")

    root.mainloop()


if __name__ == '__main__':
    main()
