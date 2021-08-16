import json
import logging
import os.path
import shutil
import sys
import tkinter
import traceback
import webbrowser
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


def is_oneloader_installed(gamepath: Path) -> bool:
    return (gamepath / "www/mods/oneloader/mod.json").exists()


def is_plutofix_installed(gamepath: Path) -> bool or None:
    filetypes_path = gamepath / "www/gomori/constants/filetypes.js"
    if not filetypes_path.exists():
        return None
    return "data_pluto" in filetypes_path.read_text(encoding="utf-8")


def are_translations_installed(gamepath: Path) -> bool:
    return (gamepath / "www/mods/omoritr/mod.json").exists()


def get_gomori_version(gamepath: Path) -> str or None:
    manifest_path = gamepath / "www/mods/gomori/mod.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))["version"]


def get_oneloader_version(gamepath: Path) -> str or None:
    manifest_path = gamepath / "www/mods/oneloader/mod.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))["version"]


def get_translation_version(gamepath: Path) -> str or None:
    manifest_path = gamepath / "www/mods/omoritr/mod.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))["version"]


def install_gomori(gomori_archive_path: Path, game_dir: Path) -> None:
    gomori_archive = zipfile.ZipFile(gomori_archive_path, "r", zipfile.ZIP_LZMA)
    gomori_archive.extractall(game_dir)


def install_oneloader(oneloader_archive_path: Path, game_dir: Path) -> None:
    oneloader_archive = zipfile.ZipFile(oneloader_archive_path, "r", zipfile.ZIP_LZMA)
    oneloader_archive.extractall(game_dir)


def install_translations(translation_archive_path: Path, game_dir: Path) -> None:
    translation_archive = zipfile.ZipFile(translation_archive_path, "r", zipfile.ZIP_LZMA)
    translation_archive.extractall(game_dir / "www/mods/")


def get_packed_tl_version(translation_archive_path: Path) -> str:
    translation_archive = zipfile.ZipFile(translation_archive_path, "r", zipfile.ZIP_LZMA)
    packed_mod_manifest = translation_archive.read("omoritr/mod.json")
    return json.loads(packed_mod_manifest)["version"]


def get_packed_gomori_version(gomori_archive_path: Path) -> str:
    translation_archive = zipfile.ZipFile(gomori_archive_path, "r", zipfile.ZIP_LZMA)
    packed_mod_manifest = translation_archive.read("www/mods/gomori/mod.json")
    return json.loads(packed_mod_manifest)["version"]


def get_packed_oneloader_version(oneloader_archive_path: Path) -> str:
    translation_archive = zipfile.ZipFile(oneloader_archive_path, "r", zipfile.ZIP_LZMA)
    packed_mod_manifest = translation_archive.read("www/mods/oneloader/mod.json")
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
    names = ["www/JSON-Patch*", "www/adm-zip*", "www/gomori", "www/mods/gomori", "www/index.html"]
    gomori_dirs = []
    for name in names:
        glob_path = str(game_dir / name)
        logging.debug(f"{glob_path = }")
        glob_result = glob(glob_path)
        logging.debug(f"{glob_result = }")
        gomori_dirs.extend(glob_result)
    logging.debug(f"{gomori_dirs = }")
    safe_delete(game_dir, gomori_dirs)


def clear_oneloader(game_dir: Path) -> None:
    safe_delete(game_dir, [game_dir / "www/modloader", game_dir / "www/mods/oneloader"])


def clear_tl(game_dir: Path) -> None:
    tl_path = game_dir / "www/mods/omoritr"
    logging.debug(f"{tl_path = }")
    if tl_path.exists():
        safe_delete(game_dir, [tl_path])


def main():
    root = tkinter.Tk()
    root.title("OMORI Türkçe Yama yükleyicisi")
    root.iconbitmap(ICON_PATH)
    root.resizable(False, False)

    installer_gui = InstallerGUI(root)

    steam_dir = None
    try:
        steam_dir = get_steam_path()
    except FileNotFoundError:
        logging.warning("Steam not found.")
        pass

    installer_gui.react_env_to_steam_dir(steam_dir)

    root.mainloop()


class InstallerGUI(tkinter.Frame):
    steam_dir: Path
    game_dir: Path

    omori_installed: bool

    gomori_installed: bool
    installed_gomori_version: str
    plutofix_installed: bool
    gomori_install_required: bool

    oneloader_installed: bool
    installed_oneloader_version: str

    tl_installed: bool
    installed_tl_version: str

    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.master = master
        self.self_frame = tkinter.Frame(master)

        # region Add tkinter widgets to self.master
        self.menu = tkinter.Menu(self.master)
        self.master.config(menu=self.menu)

        self.help_menu = tkinter.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Yardım", menu=self.help_menu)

        self.help_menu.add_command(label="İnternet sitemiz", command=lambda: webbrowser.open(ONLINE_WEBSITE))
        self.help_menu.add_command(label="Çeviride emeği geçenler", command=lambda: webbrowser.open(ONLINE_CREDITS))
        self.help_menu.add_separator()
        self.help_menu.add_command(label="Yükleyici hakkında...", command=self.onclick_about_installer)

        self.welcome_label = tkinter.Label(
            self.master,
            text="OMORI Türkçe Yama yükleyicisine hoş geldiniz.",
            justify="left", anchor="w")
        self.welcome_label.pack(fill="x", padx=5, pady=5)

        self.steam_info_label = tkinter.Label(self.master, justify="left", anchor="w")
        self.steam_info_label.pack(fill="x", padx=5, pady=5)

        self.game_location_label = tkinter.Label(
            self.master,
            text="Oyun konumu:",
            justify="left", anchor="w")
        self.game_location_label.pack(fill="x", padx=5, pady=(5, 0))

        self.game_location_entry = tkinter.Entry(self.master, justify="left")
        self.game_location_entry.pack(fill="x", padx=5, pady=(0, 5))

        self.made_checks_label = tkinter.Label(self.master, text="Yapılan kontroller:", justify="left", anchor="w")
        self.made_checks_label.pack(fill="x", padx=5, pady=(5, 0))

        self.game_installed_checkbox = tkinter.Checkbutton(
            self.master, text="OMORI yüklenmiş", state="disabled", anchor="w")
        self.game_installed_checkbox.pack(fill="x", padx=5, pady=0)

        self.gomori_installed_checkbox = tkinter.Checkbutton(
            self.master, state="disabled", anchor="w")
        self.gomori_installed_checkbox.pack(fill="x", padx=5, pady=0)

        self.plutofix_installed_checkbox = tkinter.Checkbutton(
            self.master, text="GOMORI için \"data_pluto fix\" yapılmış", state="disabled", anchor="w")
        self.plutofix_installed_checkbox.pack(fill="x", padx=5, pady=0)

        self.oneloader_installed_checkbox = tkinter.Checkbutton(
            self.master, state="disabled", anchor="w")
        self.oneloader_installed_checkbox.pack(fill="x", padx=5, pady=0)

        self.tl_installed_checkbox = tkinter.Checkbutton(
            self.master, state="disabled", anchor="w")
        self.tl_installed_checkbox.pack(fill="x", padx=5, pady=(0, 5))

        self.modloader_choice_label = tkinter.Label(
            self.master, text="Mod yükleyicisi seçimi", justify="left", anchor="w")
        self.modloader_choice_label.pack(fill="x", padx=5, pady=(5, 0))

        self.modloader_choice_var = tkinter.StringVar()

        self.modloader_choice_oneloader_radio_button = tkinter.Radiobutton(
            self.master, text="OneLoader", variable=self.modloader_choice_var, value="ONELOADER",
            command=self.react_to_modloader_selection, anchor="w")
        self.modloader_choice_oneloader_radio_button.pack(fill="x", padx=5, pady=0)

        self.modloader_choice_gomori_radio_button = tkinter.Radiobutton(
            self.master, text="GOMORI", variable=self.modloader_choice_var, value="GOMORI",
            command=self.react_to_modloader_selection, anchor="w")
        self.modloader_choice_gomori_radio_button.pack(fill="x", padx=5, pady=(0, 5))

        self.actions_required_label = tkinter.Label(
            self.master, text="Yapılması gereken işlemler:", justify="left", anchor="w")
        self.actions_required_label.pack(fill="x", padx=5, pady=(5, 0))

        self.to_install_modloader_checkbox = tkinter.Checkbutton(
            self.master, text="GOMORI yüklenecek", state="disabled", anchor="w")
        self.to_install_modloader_checkbox.pack(fill="x", padx=5)

        self.to_install_tl_checkbox = tkinter.Checkbutton(self.master, state="disabled", anchor="w")
        self.to_install_tl_checkbox.pack(fill="x", padx=5, pady=(0, 5))

        self.apply_button = tkinter.Button(self.master, text="Uygula", command=self.onclick_apply_button)
        self.apply_button.pack(pady=5, ipadx=15)

        self.credit_frame = tkinter.Frame(self.master)

        self.site_label = tkinter.Label(self.credit_frame, text="https://omori-turkce.com")
        self.site_label.pack(fill="x", side="left")
        self.team_label = tkinter.Label(self.credit_frame, text="OMORI Türkçe Çeviri Ekibi")
        self.team_label.pack(fill="x", side="right")

        self.credit_frame.pack(fill="x", side="bottom")
        # endregion

    def react_to_modloader_selection(self):
        if not hasattr(self, "steam_dir"):
            return

        self.apply_button.config(state="disabled")

        selected_modloader = self.modloader_choice_var.get()
        if selected_modloader == "GOMORI":
            if self.oneloader_installed:
                set_checkbox_state(self.to_install_modloader_checkbox, True)
                self.to_install_modloader_checkbox.config(
                    text="OneLoader, GOMORI ile değiştirilecek"
                )
            else:
                set_checkbox_state(self.to_install_modloader_checkbox, self.gomori_install_required)
                self.to_install_modloader_checkbox.config(
                    text="GOMORI \"data_plutofix\" için değiştirilecek" if self.gomori_installed else "GOMORI yüklenecek"
                )
        elif selected_modloader == "ONELOADER":
            if self.gomori_installed and self.oneloader_installed:
                set_checkbox_state(self.to_install_modloader_checkbox, False)
                self.to_install_modloader_checkbox.config(
                    text="OneLoader yüklenecek"
                )
            elif self.gomori_installed and not self.oneloader_installed:
                set_checkbox_state(self.to_install_modloader_checkbox, True)
                self.to_install_modloader_checkbox.config(
                    text="GOMORI'nin yanına OneLoader yüklenecek"
                )
            else:
                set_checkbox_state(self.to_install_modloader_checkbox, not self.oneloader_installed)
                self.to_install_modloader_checkbox.config(
                    text="OneLoader yüklenecek"
                )
        else:
            set_checkbox_state(self.to_install_modloader_checkbox, False)
            self.to_install_modloader_checkbox.config(
                text="HATA: Mod yükleyicisi seçiniz."
            )
            return

        self.apply_button.config(state="normal")

    def react_env_to_steam_dir(self, steam_dir: Path):
        logging.info(f"Steam path updated. {steam_dir = }")
        self.steam_dir = steam_dir
        self.game_dir = get_game_dir(steampath=self.steam_dir)
        logging.debug(f"{self.game_dir = }")

        self.omori_installed = self.game_dir is not None
        logging.debug(f"{self.omori_installed = }")
        self.gomori_installed = is_gomori_installed(gamepath=self.game_dir) if self.omori_installed else False
        logging.debug(f"{self.gomori_installed = }")
        self.installed_gomori_version = get_gomori_version(gamepath=self.game_dir) if self.gomori_installed else None
        logging.debug(f"{self.installed_gomori_version = }")
        self.plutofix_installed = is_plutofix_installed(gamepath=self.game_dir) if self.gomori_installed else False
        logging.debug(f"{self.plutofix_installed = }")
        self.gomori_install_required = not self.gomori_installed or not self.plutofix_installed
        logging.debug(f"{self.gomori_install_required = }")

        self.oneloader_installed = is_oneloader_installed(gamepath=self.game_dir)
        logging.debug(f"{self.oneloader_installed = }")
        self.installed_oneloader_version = get_oneloader_version(gamepath=self.game_dir) if self.oneloader_installed else None
        logging.debug(f"{self.installed_oneloader_version = }")

        self.tl_installed = are_translations_installed(gamepath=self.game_dir) if self.omori_installed else False
        logging.debug(f"{self.tl_installed = }")
        self.installed_tl_version = get_translation_version(gamepath=self.game_dir) if self.tl_installed else None
        logging.debug(f"{self.installed_tl_version = }")

        if self.gomori_installed and not self.oneloader_installed:
            self.modloader_choice_gomori_radio_button.invoke()
        else:
            self.modloader_choice_oneloader_radio_button.invoke()

        self.react_widgets_to_env()

    def react_widgets_to_env(self):
        if not self.omori_installed:
            self.steam_info_label.config(
                text="Bilgisayarınızda OMORI tespit edilememiştir.\n"
                     "Lütfen bilgisayarınıza OMORI yükleyip bu programı tekrar çalıştırın.",
                fg="#FF0000"
            )
            self.game_location_entry.delete(0, tkinter.END)
            self.game_location_entry.insert(0, "HATA: OMORI oyununu yükleyip bu programı tekrar çalıştırın.")
            self.game_location_entry.config(state="disabled")  # self.game_location_entry.config(state="normal")
            self.apply_button.config(state="disabled")
        else:
            self.steam_info_label.config(
                text="OMORI bilgisayarınızda otomatik olarak tespit edilmiştir.\n"
                     "Bilgileri inceleyip düğmeye tıklayarak yamayı yükleyebilirsiniz.",
                fg="#000000"
            )
            self.game_location_entry.delete(0, tkinter.END)
            self.game_location_entry.insert(0, os.path.realpath(self.game_dir))
            self.game_location_entry.config(state="disabled")
            self.apply_button.config(state="normal")

        set_checkbox_state(self.game_installed_checkbox, self.omori_installed)
        set_checkbox_state(
            checkbox=self.gomori_installed_checkbox, condition=self.gomori_installed,
            true_text=f"GOMORI yüklenmiş ({self.installed_gomori_version})",
            false_text="GOMORI yüklenmiş"
        )
        set_checkbox_state(self.plutofix_installed_checkbox, self.plutofix_installed)
        set_checkbox_state(
            checkbox=self.oneloader_installed_checkbox, condition=self.oneloader_installed,
            true_text=f"OneLoader yüklenmiş ({self.installed_oneloader_version})",
            false_text="OneLoader yüklenmiş"
        )

        set_checkbox_state(
            checkbox=self.tl_installed_checkbox, condition=self.tl_installed,
            true_text=f"Türkçe Yama yüklenmiş ({self.installed_tl_version})",
            false_text="Türkçe Yama yüklenmiş"
        )

        set_checkbox_state(self.to_install_tl_checkbox, True)
        self.to_install_tl_checkbox.config(
            text="".join([
                "Türkçe Yama ",
                "değiştirilecek (yeni: " if self.tl_installed else "yüklenecek (",
                PACKED_TL_VERSION,
                ")"
            ])
        )

        self.react_to_modloader_selection()

    def onclick_apply_button(self):
        tmp_click_sponge = tkinter.Toplevel(self.master)
        tmp_click_sponge.grab_set()
        tmp_click_sponge.title("")
        tmp_click_sponge.iconbitmap(ICON_PATH)
        tmp_click_sponge.resizable(False, False)

        logging.info("Applying operations...")

        try:
            selected_modloader = self.modloader_choice_var.get()
            logging.debug(f"{selected_modloader = }")
            if selected_modloader == "GOMORI":
                if self.oneloader_installed:
                    logging.info("Uninstalling OneLoader...")
                    clear_oneloader(game_dir=self.game_dir)
                    logging.info("Installing GOMORI...")
                    install_gomori(gomori_archive_path=GOMORI_ARCHIVE_PATH, game_dir=self.game_dir)
                elif self.gomori_install_required:
                    logging.info("Uninstalling GOMORI...")
                    clear_gomori(game_dir=self.game_dir)
                    logging.info("Installing OMORI...")
                    install_gomori(gomori_archive_path=GOMORI_ARCHIVE_PATH, game_dir=self.game_dir)

            if selected_modloader == "ONELOADER":
                if not self.oneloader_installed:
                    logging.info("Installing OneLoader...")
                    install_oneloader(oneloader_archive_path=ONELOADER_ARCHIVE_PATH, game_dir=self.game_dir)

            if self.tl_installed:
                logging.info("Uninstalling translations...")
                clear_tl(game_dir=self.game_dir)

            logging.info("Installing translations...")
            install_translations(translation_archive_path=TL_ARCHIVE_PATH, game_dir=self.game_dir)
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            formatted_exception = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

            logging.critical(formatted_exception)

            alert = tkinter.Toplevel(self.master)
            alert.grab_set()
            alert.title("OMORI Türkçe Yama yükleyicisi")
            alert.iconbitmap(ICON_PATH)
            alert.resizable(False, False)

            tkinter.Label(alert, text="OMORI Türkçe Yama yükleme işlemi sırasında beklenmeyen bir hata oluştu.") \
                .pack(fill="x", padx=5, pady=5)

            stacktrace_widget = tkinter.Text(alert, width=100, height=20)
            stacktrace_widget.insert("1.0", formatted_exception)
            stacktrace_widget.pack(fill="x", padx=5, pady=5)
        else:
            alert = tkinter.Toplevel(self.master)
            alert.grab_set()
            alert.title("OMORI Türkçe Yama yükleyicisi")
            alert.iconbitmap(ICON_PATH)
            alert.resizable(False, False)

            tkinter.Label(alert, text="OMORI Türkçe Yama yükleme işlemi hatasızca tamamlanmıştır.") \
                .pack(fill="x", padx=15, pady=(15, 5))

            tkinter.Button(alert, text="Tamam", command=alert.destroy) \
                .pack(ipadx=15, padx=15, pady=(5, 15))

        tmp_click_sponge.destroy()

        self.react_env_to_steam_dir(self.steam_dir)

    def onclick_about_installer(self):
        about_window = tkinter.Toplevel(self.master)
        about_window.grab_set()
        about_window.title("OMORI Türkçe Yama yükleyicisi hakkında")
        about_window.iconbitmap(ICON_PATH)
        about_window.resizable(False, False)

        tkinter.Label(
            about_window, anchor="w", justify="left",
            text="OMORI Türkçe Yama yükleyicisi"
        ).pack(fill="x", padx=(55, 15), pady=(10, 0))

        ABOUT_WRAPLENGTH = 400

        tkinter.Label(
            about_window, anchor="w", justify="left",
            text=f"Yükleyici Sürüm 2, Çeviri Sürüm {PACKED_TL_VERSION}"
        ).pack(fill="x", padx=(55, 15), pady=(0, 20))

        tkinter.Label(
            about_window, anchor="w", justify="left", wraplength=ABOUT_WRAPLENGTH,
            text="Bu yükleyici OMORI Türkçe Çeviri Ekibi için Emre Özcan tarafından hazırlanmıştır ve "
                 "OMORI Türkçe Çeviri Ekibi'ne dağıtım hakkı tanınmıştır."
        ).pack(fill="x", padx=(55, 15))

        tkinter.Label(
            about_window, anchor="w", justify="left", wraplength=ABOUT_WRAPLENGTH,
            text="emreis.com"
        ).pack(fill="x", padx=(55, 15))

        tkinter.Label(
            about_window, anchor="w", justify="left", wraplength=ABOUT_WRAPLENGTH,
            text="OMORI Türkçe Çeviri Ekibi ikonu © 2021 claus"
        ).pack(fill="x", padx=(55, 15), pady=(30, 0))
        tkinter.Label(
            about_window, anchor="w", justify="left", wraplength=ABOUT_WRAPLENGTH,
            text="Yükleyici © 2021 Emre Özcan emreis.com"
        ).pack(fill="x", padx=(55, 15), pady=(0, 20))

        tkinter.Label(
            about_window, anchor="w", justify="left", wraplength=ABOUT_WRAPLENGTH,
            text=f"GOMORI ({PACKED_GOMORI_VERSION}) © 2021 Gijs Hogervorst - Licensed under the MIT License"
        ).pack(fill="x", padx=(55, 15), pady=(5, 0))

        tkinter.Label(
            about_window, anchor="w", justify="left", wraplength=ABOUT_WRAPLENGTH,
            text=f"OneLoader ({PACKED_ONELOADER_VERSION}) © 2021 Rph - Licensed under the MIT License"
        ).pack(fill="x", padx=(55, 15), pady=(0, 5))

        tkinter.Label(
            about_window, anchor="w", justify="left", wraplength=ABOUT_WRAPLENGTH,
            text="UYARI: Bu yükleyicinin dağıtım hakkı yalnızca OMORI Türkçe Çeviri Ekibi'ne verilmiştir. Başkaları "
                 "tarafından dağıtılamaz. Yeniden dağıtmayınız, https://omori-turkce.com/indir sayfasına bağlantı "
                 "veriniz."
        ).pack(fill="x", padx=(55, 15), pady=(10, 20))


def set_checkbox_state(checkbox: tkinter.Checkbutton, condition: bool, true_text: str or None = None,
                       false_text: str or None = None):
    if condition:
        checkbox.select()
        if true_text is not None:
            checkbox.config(
                text=true_text
            )
    else:
        checkbox.deselect()
        if false_text is not None:
            checkbox.config(
                text=false_text
            )


if __name__ == '__main__':
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        level=logging.DEBUG,
        filename="omoritr-installer.log"
    )

    logging.info("Starting omoritr-installer")
    logging.info("OMORI Türkçe Çeviri Ekibi, 2021")
    logging.info("https://omori-turkce.com")
    logging.info("Emre Özcan github.com/emreozcan")

    BUNDLE_DIR = Path(__file__).parent
    GOMORI_ARCHIVE_PATH = Path.cwd() / BUNDLE_DIR / "res/gomori.zip"
    ONELOADER_ARCHIVE_PATH = Path.cwd() / BUNDLE_DIR / "res/oneloader.zip"
    TL_ARCHIVE_PATH = Path.cwd() / BUNDLE_DIR / "res/omoritr.zip"
    ICON_PATH = Path.cwd() / BUNDLE_DIR / "res/transparent-256.ico"

    PACKED_TL_VERSION = get_packed_tl_version(TL_ARCHIVE_PATH)
    PACKED_GOMORI_VERSION = get_packed_gomori_version(GOMORI_ARCHIVE_PATH)
    PACKED_ONELOADER_VERSION = get_packed_oneloader_version(ONELOADER_ARCHIVE_PATH)

    ONLINE_WEBSITE = "https://omori-turkce.com"
    ONLINE_CREDITS = "https://omori-turkce.com/emegi-gecenler"

    main()
