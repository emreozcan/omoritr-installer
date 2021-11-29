import asyncio
import dataclasses
import json
import logging
import os.path
import shutil
import sys
import tempfile
import threading
import tkinter
import traceback
import urllib.request
import webbrowser
import winreg
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


def get_installed_gomori_version(gamepath: Path) -> str or None:
    manifest_path = gamepath / "www/mods/gomori/mod.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))["version"]


def get_installed_oneloader_version(gamepath: Path) -> str or None:
    manifest_path = gamepath / "www/mods/oneloader/mod.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))["version"]


def get_installed_translation_version(gamepath: Path) -> str or None:
    manifest_path = gamepath / "www/mods/omoritr/mod.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))["version"]


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


def main(event_loop):
    urllib.request.urlcleanup()

    root = tkinter.Tk()
    root.title("OMORI Türkçe Yama Yükleyicisi")
    root.iconbitmap(ICON_PATH)
    root.resizable(False, False)

    installer_gui = InstallerGUI(master=root, event_loop=event_loop)

    steam_dir = None
    try:
        steam_dir = get_steam_path()
    except FileNotFoundError:
        logging.warning("Steam not found.")

    installer_gui.react_env_to_steam_dir(steam_dir)

    threading.Thread(
        target=lambda: event_loop.run_until_complete(installer_gui.request_and_react_to_manifest())
    ).start()

    root.mainloop()


@dataclasses.dataclass
class PackageManifest:
    name: str
    path: str
    filename: str
    version: str
    target: str

    def install(self, game_dir: Path):
        download_directory = tempfile.TemporaryDirectory(prefix="omori-turkce-package-")
        filename, _ = urllib.request.urlretrieve(self.path, Path(download_directory.name) / self.filename)
        extract_target = game_dir / self.target
        if not os.path.realpath(extract_target).startswith(os.path.realpath(game_dir)):
            raise RuntimeError(f"{self.name}: Manifesto hedefi ({self.target}) geçersiz.")
        shutil.unpack_archive(filename=filename, extract_dir=extract_target)
        download_directory.cleanup()


@dataclasses.dataclass
class PackageState:
    version: str = "?"
    found: bool = False

    manifest: PackageManifest = None


@dataclasses.dataclass
class PackageIndex:
    gomori: PackageState = dataclasses.field(default_factory=PackageState)
    plutofix: PackageState = dataclasses.field(default_factory=PackageState)
    oneloader: PackageState = dataclasses.field(default_factory=PackageState)
    translations: PackageState = dataclasses.field(default_factory=PackageState)


def onclick_show_debug_dump():
    webbrowser.open("omoritr-installer.log")


class InstallerGUI(tkinter.Frame):
    steam_dir: Path
    game_dir: Path

    omori_installed: bool
    gomori_install_required: bool

    candidate_packages: PackageIndex = PackageIndex()
    installed_packages: PackageIndex = PackageIndex()

    def __init__(self, master, event_loop, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.master = master
        self.event_loop = event_loop

        self.self_frame = tkinter.Frame(master)

        # region Add tkinter widgets to self.master
        self.menu = tkinter.Menu(self.master)
        self.master.config(menu=self.menu)

        self.help_menu = tkinter.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Yardım", menu=self.help_menu)

        self.help_menu.add_command(label="Yükleyici hakkında...", command=self.onclick_about_installer)
        self.help_menu.add_separator()
        self.help_menu.add_command(label="İnternet sitemiz", command=lambda: webbrowser.open(ONLINE_WEBSITE))
        self.help_menu.add_command(label="Çeviride emeği geçenler", command=lambda: webbrowser.open(ONLINE_CREDITS))
        self.help_menu.add_separator()
        self.help_menu.add_command(label="Hata ayıklama dökümünü görüntüle", command=onclick_show_debug_dump)

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

        self.apply_button = tkinter.Button(self.master, command=self.onclick_apply_button)
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
            if self.installed_packages.oneloader.found:
                set_checkbox_state(self.to_install_modloader_checkbox, True)
                self.to_install_modloader_checkbox.config(
                    text=f"OneLoader {self.installed_packages.oneloader.version}, "
                         f"GOMORI {self.candidate_packages.gomori.version} ile değiştirilecek"
                )
            else:
                set_checkbox_state(self.to_install_modloader_checkbox, self.gomori_install_required)
                if self.installed_packages.gomori.found:
                    self.to_install_modloader_checkbox.config(
                        text=f"GOMORI {self.installed_packages.gomori.version}, "
                             f"\"data_plutofix\" için değiştirilecek"
                    )
                else:
                    self.to_install_modloader_checkbox.config(
                        text=f"GOMORI {self.candidate_packages.gomori.version} yüklenecek"
                    )
        elif selected_modloader == "ONELOADER":
            if self.installed_packages.gomori.found and self.installed_packages.oneloader.found:
                set_checkbox_state(self.to_install_modloader_checkbox, False)
                self.to_install_modloader_checkbox.config(
                    text=f"OneLoader {self.candidate_packages.oneloader.version} yüklenecek"
                )
            elif self.installed_packages.gomori.found and not self.installed_packages.oneloader.found:
                set_checkbox_state(self.to_install_modloader_checkbox, True)
                self.to_install_modloader_checkbox.config(
                    text=f"GOMORI'nin ({self.installed_packages.gomori.version}) yanına "
                         f"OneLoader {self.candidate_packages.oneloader.version} yüklenecek"
                )
            else:
                set_checkbox_state(self.to_install_modloader_checkbox, not self.installed_packages.oneloader.found)
                self.to_install_modloader_checkbox.config(
                    text=f"OneLoader {self.candidate_packages.oneloader.version} yüklenecek"
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

        if self.omori_installed:
            self.installed_packages.gomori.found = is_gomori_installed(gamepath=self.game_dir)
            if self.installed_packages.gomori.found:
                self.installed_packages.gomori.version = get_installed_gomori_version(gamepath=self.game_dir)
                self.installed_packages.plutofix.found = is_plutofix_installed(gamepath=self.game_dir)
                self.gomori_install_required = \
                    not self.installed_packages.gomori.found \
                    or not self.installed_packages.plutofix.found
            else:
                self.gomori_install_required = True

            self.installed_packages.oneloader.found = is_oneloader_installed(gamepath=self.game_dir)
            if self.installed_packages.oneloader.found:
                self.installed_packages.oneloader.version = get_installed_oneloader_version(gamepath=self.game_dir)

            self.installed_packages.translations.found = are_translations_installed(gamepath=self.game_dir)
            if self.installed_packages.translations.found:
                self.installed_packages.translations.version = get_installed_translation_version(gamepath=self.game_dir)

            if self.installed_packages.gomori.found and not self.installed_packages.oneloader.found:
                self.modloader_choice_gomori_radio_button.invoke()
            else:
                self.modloader_choice_oneloader_radio_button.invoke()

        logging.debug(f"{self.installed_packages = }")
        logging.debug(f"{self.gomori_install_required = }")

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
            checkbox=self.gomori_installed_checkbox, condition=self.installed_packages.gomori.found,
            true_text=f"GOMORI yüklenmiş ({self.installed_packages.gomori.version})",
            false_text="GOMORI yüklenmiş"
        )
        set_checkbox_state(self.plutofix_installed_checkbox, self.installed_packages.plutofix.found)
        set_checkbox_state(
            checkbox=self.oneloader_installed_checkbox, condition=self.installed_packages.oneloader.found,
            true_text=f"OneLoader yüklenmiş ({self.installed_packages.oneloader.version})",
            false_text="OneLoader yüklenmiş"
        )

        set_checkbox_state(
            checkbox=self.tl_installed_checkbox, condition=self.installed_packages.translations.found,
            true_text=f"Türkçe Yama yüklenmiş ({self.installed_packages.translations.version})",
            false_text="Türkçe Yama yüklenmiş"
        )

        set_checkbox_state(self.to_install_tl_checkbox, True)
        if self.installed_packages.translations.found:
            self.to_install_tl_checkbox.config(
                text=f"Türkçe Yama değiştirilecek (yeni: {self.candidate_packages.translations.version})"
            )
        else:
            self.to_install_tl_checkbox.config(
                text=f"Türkçe Yama yüklenecek ({self.candidate_packages.translations.version})"
            )

        if NETWORK_MODE_ENABLED:
            self.apply_button.config(text="Gerekli Paketleri İndir ve Uygula")
        else:
            self.apply_button.config(text="Uygula")

        self.react_to_modloader_selection()

    def onclick_apply_button(self):
        waiting_area = tkinter.Toplevel(self.master)
        waiting_area.grab_set()
        waiting_area.title("Bekleme Alanı")
        waiting_area.iconbitmap(ICON_PATH)
        waiting_area.resizable(False, False)

        if NETWORK_MODE_ENABLED:
            wait_text = "Gerekli paketler indirilip seçeneklerinize göre yerleştirilecek. " \
                        "İnternet bağlantınıza göre biraz uzun sürebilir, lütfen sabırla bekleyiniz."
        else:
            wait_text = "Paketler seçeneklerinize göre yerleştiriliyor. Lütfen sabırla bekleyiniz."

        tkinter.Label(
            waiting_area, anchor="w", justify="left", wraplength=400,
            text=wait_text
        ).pack(fill="x", padx=15, pady=15)

        def apply_operations():
            self.event_loop.run_until_complete(self.apply_operations())
            waiting_area.destroy()
            self.react_env_to_steam_dir(self.steam_dir)

        threading.Thread(target=apply_operations).start()

    async def apply_operations(self):
        logging.info("Applying operations...")

        if self.candidate_packages.translations.manifest is None:
            self.show_alert_message_modal(
                message="Çeviri yükleme manifestosu çevrimiçi olarak alınamadığı için yükleme işlemi yapılamaz."
            )
            return

        try:
            selected_modloader = self.modloader_choice_var.get()
            logging.debug(f"{selected_modloader = }")

            if selected_modloader == "GOMORI":
                if self.installed_packages.oneloader.found:
                    logging.info("Uninstalling OneLoader...")
                    clear_oneloader(game_dir=self.game_dir)
                    logging.info("Installing GOMORI...")
                    self.candidate_packages.gomori.manifest.install(game_dir=self.game_dir)

                elif self.gomori_install_required:
                    logging.info("Uninstalling GOMORI...")
                    clear_gomori(game_dir=self.game_dir)
                    logging.info("Installing GOMORI...")
                    self.candidate_packages.gomori.manifest.install(game_dir=self.game_dir)

            if selected_modloader == "ONELOADER":
                if not self.installed_packages.oneloader.found:
                    logging.info("Installing OneLoader...")
                    self.candidate_packages.oneloader.manifest.install(game_dir=self.game_dir)

            if self.installed_packages.translations.found:
                logging.info("Uninstalling translations...")
                clear_tl(game_dir=self.game_dir)

            logging.info("Installing translations...")
            self.candidate_packages.translations.manifest.install(game_dir=self.game_dir)
        except Exception:
            self.show_traceback_window()
            return
        else:
            self.show_alert_message_modal("OMORI Türkçe Yama yükleme işlemi hatasızca tamamlanmıştır.")

    def show_traceback_window(self):
        exc_type, exc_value, exc_traceback = sys.exc_info()
        formatted_exception = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        logging.critical(formatted_exception)

        alert = tkinter.Toplevel(self.master)
        alert.grab_set()
        alert.title("Hata Raporlayıcı")
        alert.iconbitmap(ICON_PATH)
        alert.resizable(False, False)

        tkinter.Label(alert, text="OMORI Türkçe Yama yükleme işlemi sırasında beklenmeyen bir hata oluştu.") \
            .pack(fill="x", padx=5, pady=5)

        stacktrace_widget = tkinter.Text(alert, width=100, height=20)
        stacktrace_widget.insert("1.0", formatted_exception)
        stacktrace_widget.pack(fill="x", padx=5, pady=5)

    def onclick_about_installer(self):
        about_window = tkinter.Toplevel(self.master)
        about_window.grab_set()
        about_window.title("OMORI Türkçe Yama Yükleyicisi hakkında")
        about_window.iconbitmap(ICON_PATH)
        about_window.resizable(False, False)

        about_text = \
            "OMORI Türkçe Yama yükleyicisi\n" \
            "Sürüm 3\n" \
            "Copyright 2021-2022, Emre Özcan. Tüm hakları saklıdır.\n" \
            "\n" \
            "OMORI Türkçe Çeviri Ekibi ikonu Copyright 2021, claus.\n" \
            "\n\n\n" \
            "UYARI: Bu program 5846 sayılı Fikir ve Sanat Eserleri Kanunu uyarınca korunmaktadır. Dağıtımı serbest " \
            "değildir. Yeniden dağıtmayınız, https://omori-turkce.com/indir sayfasına bağlantı veriniz."

        tkinter.Label(
            about_window, anchor="w", justify="left", wraplength=400, text=about_text
        ).pack(fill="x", padx=(55, 15), pady=20)

    async def request_and_react_to_manifest(self):
        if not NETWORK_MODE_ENABLED:
            return

        try:
            manifest = json.loads(urllib.request.urlopen(MANIFEST_URL).read().decode("utf-8"))
        except Exception as e:
            self.show_alert_message_modal(f"Yama yükleme manifestosu internetten alınırken bir hata oluştu.\n\n{e}")
            return

        if manifest["manifestVersion"] != 1:
            self.show_alert_message_modal(
                message="İnternetten alınan yama yükleme manifestosunu yükleyicinin bu sürümü anlayamıyor. Lütfen "
                        "https://omori-turkce.com/indir adresine giderek yükleyicinin daha yeni bir sürümünü edinin.",
                title="Hata Raporlayıcı"
            )
            return

        index = {name: PackageState(version=data["version"], manifest=PackageManifest(name=name, **data))
                 for name, data in manifest["packages"].items()}
        self.candidate_packages = PackageIndex(**index)

        logging.debug(f"{manifest = }")
        logging.debug(f"{self.candidate_packages = }")

        self.react_widgets_to_env()

    def show_alert_message_modal(self, message: str, title: str = "Durum Penceresi", button_text: str = "Tamam",
                                 wraplength: int = 350, label_kwargs=None, label_pack_kwargs=None, button_kwargs=None,
                                 button_pack_kwargs=None):
        if label_kwargs is None:
            label_kwargs = {}
        if label_pack_kwargs is None:
            label_pack_kwargs = {}
        if button_kwargs is None:
            button_kwargs = {}
        if button_pack_kwargs is None:
            button_pack_kwargs = {}

        alert = tkinter.Toplevel(self.master)
        alert.grab_set()
        alert.title(title)
        alert.iconbitmap(ICON_PATH)
        alert.resizable(False, False)

        label = tkinter.Label(alert, anchor="w", justify="left", wraplength=wraplength, text=message, **label_kwargs) \
            .pack(fill="x", padx=15, pady=15, **label_pack_kwargs)

        button = tkinter.Button(alert, text=button_text, command=alert.destroy, **button_kwargs) \
            .pack(ipadx=15, padx=15, pady=(5, 15), **button_pack_kwargs)

        return [alert, label, button]


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
    logging.info("Commisioned from Emre Özcan by OMORI Türkçe Çeviri Ekibi")
    logging.info("Copyright 2021-2022, Emre Özcan. All rights reserved.")
    logging.info("https://omori-turkce.com")

    NETWORK_MODE_ENABLED = True

    MANIFEST_URL = "https://raw.githubusercontent.com/omoritr/downloads/master/manifest.json"

    BUNDLE_DIR = Path(__file__).parent
    ICON_PATH = BUNDLE_DIR / "res/transparent-256.ico"

    ONLINE_WEBSITE = "https://omori-turkce.com"
    ONLINE_CREDITS = "https://omori-turkce.com/emegi-gecenler"

    ASYNC_LOOP = asyncio.get_event_loop()

    main(ASYNC_LOOP)
