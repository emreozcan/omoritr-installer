#  Copyright 2021-2023 Emre Özcan
#
#  installer.py
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import asyncio
import dataclasses
import json
import logging
import logging.handlers
import os.path
import re
import shutil
import sys
import tempfile
import threading
import tkinter
import tkinter.ttk
import traceback
import winreg
from glob import glob
from pathlib import Path
from webbrowser import open as wopen
from zipfile import ZipFile

import requests


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
    LOG.warning(f"Collecting strings from {library_map_file = }")
    matches = re.finditer(r"\n\t*\"path\"\t\t\"(.+)\"\n", library_map_file.read_text("utf-8"))
    for match in matches:
        path_string = match.groups()[0]
        candidate_path = Path(path_string)
        LOG.debug(f"Checking library candidate {candidate_path = }")
        if not candidate_path.is_absolute():
            LOG.warning(" -> Path isn't absolute.")
            continue
        if not candidate_path.exists():
            LOG.debug(" -> Path doesn't exist.")
            continue
        LOG.debug(" -> Path exists.")
        candidate_exec_path = candidate_path / "steamapps/common/OMORI/OMORI.exe"
        if candidate_exec_path.exists():
            LOG.debug(" -> It has OMORI.")
            game_dir = candidate_exec_path.parent
            LOG.info(f"Game found at {game_dir = }")
            return game_dir
        LOG.debug(" -> It doesn't have OMORI.")
    return None


def is_gomori_installed(gamepath: Path) -> bool:
    return (gamepath / "www/gomori/gomori.js").exists()


def is_oneloader_installed(gamepath: Path) -> bool:
    return (gamepath / "www/mods/oneloader/mod.json").exists()


def are_translations_installed(gamepath: Path) -> bool:
    return (gamepath / "www/mods/omoritr.zip").exists() ^ (gamepath / "www/mods/omoritr/mod.json").exists()


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
    loose_manifest_path = gamepath / "www/mods/omoritr/mod.json"
    mod_archive_path = gamepath / "www/mods/omoritr.zip"
    if not are_translations_installed(gamepath):
        return None
    if mod_archive_path.exists():
        try:
            with ZipFile(mod_archive_path, "r") as mod_archive:
                manifest_contents = mod_archive.read("mod.json")
        except KeyError:
            return "hatalı yükleme"
    else:
        manifest_contents = loose_manifest_path.read_text(encoding="utf-8")
    return json.loads(manifest_contents)["version"]


def safe_delete(container: Path or str, paths: list[Path or str]) -> None:
    LOG.warning("Collecting information for delete operation")
    real_container_path = os.path.realpath(container)
    LOG.debug(f"{container = }")
    LOG.warning(f"{real_container_path = }")
    for target_path in paths:
        LOG.warning(f" -- Collecting information about {target_path = }")
        real_target_path = os.path.realpath(target_path)
        LOG.debug(f"{target_path = }")
        LOG.warning(f"{real_target_path = }")
        if not os.path.exists(real_target_path):
            LOG.error("This file does not exist. Why?")
            continue
        if not real_target_path.startswith(real_container_path):
            LOG.error("This file is not inside the container. Why?")
            continue
        if os.path.isdir(real_target_path):
            LOG.debug("Path is a directory. Performing recursive directory deleting operation.")
            shutil.rmtree(real_target_path)
        else:
            LOG.debug("Path is not a directory. Performing unlinking operation.")
            os.unlink(real_target_path)


def clear_gomori(game_dir: Path) -> None:
    names = ["www/JSON-Patch*", "www/adm-zip*", "www/gomori", "www/mods/gomori", "www/index.html"]
    gomori_dirs = []
    for name in names:
        glob_path = str(game_dir / name)
        LOG.debug(f"{glob_path = }")
        glob_result = glob(glob_path)
        LOG.debug(f"{glob_result = }")
        gomori_dirs.extend(glob_result)
    LOG.debug(f"{gomori_dirs = }")
    safe_delete(game_dir, gomori_dirs)


def clear_oneloader(game_dir: Path) -> None:
    safe_delete(game_dir, [game_dir / "www/modloader", game_dir / "www/mods/oneloader"])


def clear_tl(game_dir: Path) -> None:
    safe_delete(
        game_dir,
        [
            game_dir / "www/mods/omoritr",
            game_dir / "www/mods/omoritr.zip"
        ]
    )


def main(event_loop):
    root = tkinter.Tk()
    root.title("OMORI Türkçe Yama Yükleyicisi")
    root.iconbitmap(ICON_PATH)
    root.resizable(False, False)

    installer_gui = InstallerGUI(master=root, event_loop=event_loop)

    steam_dir = None
    try:
        steam_dir = get_steam_path()
    except FileNotFoundError:
        LOG.warning("Steam not found.")

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

    def install(self, game_dir: Path, report_hook: callable = None):
        download_directory = tempfile.TemporaryDirectory(prefix="omori-turkce-package-")
        downloaded_archive_path = Path(download_directory.name) / self.filename
        with open(downloaded_archive_path, "wb") as downloaded_file:
            response = requests.get(self.path, stream=True)
            total_length = response.headers.get("content-length")
            if total_length is None:
                downloaded_file.write(response.content)
            else:
                downloaded_length = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size=4096):
                    downloaded_length += len(data)
                    downloaded_file.write(data)
                    report_hook(downloaded_length, 1, total_length)
        extract_target = game_dir / self.target
        if not os.path.realpath(extract_target).startswith(os.path.realpath(game_dir)):
            raise RuntimeError(f"{self.name}: Manifesto hedefi ({self.target}) geçersiz.")
        shutil.unpack_archive(filename=downloaded_archive_path, extract_dir=extract_target)
        download_directory.cleanup()


@dataclasses.dataclass
class PackageState:
    version: str = "?"
    found: bool = False

    manifest: PackageManifest = None


@dataclasses.dataclass
class PackageIndex:
    gomori: PackageState = dataclasses.field(default_factory=PackageState)
    oneloader: PackageState = dataclasses.field(default_factory=PackageState)
    translations: PackageState = dataclasses.field(default_factory=PackageState)


class InstallerGUI(tkinter.Frame):
    steam_dir: Path
    game_dir: Path

    omori_installed: bool

    will_install_oneloader = True

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

        self.file_menu = tkinter.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Dosya", menu=self.file_menu)

        self.file_menu.add_command(label="Yenile", command=self.refresh)

        self.help_menu = tkinter.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Yardım", menu=self.help_menu)

        self.help_menu.add_command(label="Yükleyici hakkında...", command=self.onclick_about_installer)
        self.help_menu.add_separator()
        self.help_menu.add_command(label="İnternet sitemiz", command=lambda: wopen(ONLINE_WEBSITE))
        self.help_menu.add_command(label="Çeviride emeği geçenler", command=lambda: wopen(ONLINE_CREDITS))
        self.help_menu.add_separator()
        self.help_menu.add_command(label="Hata ayıklama dökümünü görüntüle", command=lambda: wopen(LOG_FILE))

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

        self.oneloader_installed_checkbox = tkinter.Checkbutton(
            self.master, state="disabled", anchor="w")
        self.oneloader_installed_checkbox.pack(fill="x", padx=5, pady=0)

        self.tl_installed_checkbox = tkinter.Checkbutton(
            self.master, state="disabled", anchor="w")
        self.tl_installed_checkbox.pack(fill="x", padx=5, pady=(0, 5))

        self.actions_required_label = tkinter.Label(
            self.master, text="Yapılması gereken işlemler:", justify="left", anchor="w")
        self.actions_required_label.pack(fill="x", padx=5, pady=(5, 0))

        self.to_install_modloader_checkbox = tkinter.Checkbutton(
            self.master, text="Mod yükleyici yüklenecek", state="disabled", anchor="w")
        self.to_install_modloader_checkbox.pack(fill="x", padx=5)

        self.goneloader_warning_label = tkinter.Label(self.master, justify="left", anchor="w")
        self.goneloader_warning_label.pack(fill="x", padx=5, pady=5)

        self.to_install_tl_checkbox = tkinter.Checkbutton(self.master, state="disabled", anchor="w")
        self.to_install_tl_checkbox.pack(fill="x", padx=5, pady=(0, 5))

        self.apply_button = tkinter.Button(
            self.master, command=self.onclick_apply_button, state="disabled", text="Gerekli Paketleri İndir ve Uygula"
        )
        self.apply_button.pack(pady=5, ipadx=15)

        self.credit_frame = tkinter.Frame(self.master)

        self.site_label = tkinter.Label(self.credit_frame, text="https://omori-turkce.com")
        self.site_label.pack(fill="x", side="left")
        self.team_label = tkinter.Label(self.credit_frame, text="OMORI Türkçe Çeviri Ekibi")
        self.team_label.pack(fill="x", side="right")

        self.credit_frame.pack(fill="x", side="bottom")
        # endregion

    def react_env_to_steam_dir(self, steam_dir: Path):
        LOG.info(f"Steam path updated. {steam_dir = }")
        self.steam_dir = steam_dir
        self.game_dir = get_game_dir(steampath=self.steam_dir)
        LOG.debug(f"{self.game_dir = }")

        self.omori_installed = self.game_dir is not None
        LOG.debug(f"{self.omori_installed = }")

        if self.omori_installed:
            self.installed_packages.gomori.found = is_gomori_installed(gamepath=self.game_dir)
            if self.installed_packages.gomori.found:
                self.installed_packages.gomori.version = get_installed_gomori_version(gamepath=self.game_dir)

            self.installed_packages.oneloader.found = is_oneloader_installed(gamepath=self.game_dir)
            if self.installed_packages.oneloader.found:
                self.installed_packages.oneloader.version = get_installed_oneloader_version(gamepath=self.game_dir)

            self.installed_packages.translations.found = are_translations_installed(gamepath=self.game_dir)
            if self.installed_packages.translations.found:
                self.installed_packages.translations.version = get_installed_translation_version(gamepath=self.game_dir)

        LOG.debug(f"{self.installed_packages = }")
        LOG.debug(f"{self.omori_installed = }")

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

        self.will_install_oneloader = not (
                self.installed_packages.oneloader.found and
                self.installed_packages.oneloader.version == self.candidate_packages.oneloader.version
        )

        set_checkbox_state(self.game_installed_checkbox, self.omori_installed)
        set_checkbox_state(
            checkbox=self.gomori_installed_checkbox, condition=self.installed_packages.gomori.found,
            true_text=f"GOMORI yüklenmiş ({self.installed_packages.gomori.version})",
            false_text="GOMORI yüklenmiş"
        )

        if not self.installed_packages.gomori.found:
            self.gomori_installed_checkbox.pack_forget()

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

        set_checkbox_state(self.to_install_modloader_checkbox, self.will_install_oneloader)

        if self.installed_packages.gomori.found:
            self.to_install_modloader_checkbox.config(
                text=f"GOMORI'nin ({self.installed_packages.gomori.version}) yanına "
                     f"OneLoader {self.candidate_packages.oneloader.version} yüklenecek"
            )
            self.goneloader_warning_label.config(
                text="GOMORI yüklenmiş oyuna OneLoader yüklemek önerilmemektedir.\n"
                     "Oyunu silip baştan yüklemeniz şiddetle tavsiye edilir.\n"
                     "Oluşan hatalarda destek sağlanmayacaktır.",
                fg="#FF0000"
            )
        else:
            self.to_install_modloader_checkbox.config(
                text=f"OneLoader {self.candidate_packages.oneloader.version} yüklenecek"
            )
            self.goneloader_warning_label.pack_forget()

    def onclick_apply_button(self):
        waiting_area = tkinter.Toplevel(self.master)
        waiting_area.grab_set()
        waiting_area.title("Bekleme Alanı")
        waiting_area.iconbitmap(ICON_PATH)
        waiting_area.resizable(False, False)

        if self.will_install_oneloader:
            tkinter.Label(
                waiting_area, anchor="w", justify="left", wraplength=400,
                text="OneLoader indirme ilerlemesi:"
            ).pack(fill="x", padx=5, pady=(5, 0))

            oneloader_progress = tkinter.ttk.Progressbar(waiting_area)
            oneloader_progress.configure(
                length=400, orient="horizontal", mode="determinate", maximum=100
            )
            oneloader_progress.pack(fill="x", padx=5, pady=(0, 5))
        else:
            oneloader_progress = tkinter.ttk.Progressbar()

        tkinter.Label(
            waiting_area, anchor="w", justify="left", wraplength=400,
            text="Türkçe Yama indirme ilerlemesi:"
        ).pack(fill="x", padx=5, pady=(5, 0))

        translations_progress = tkinter.ttk.Progressbar(waiting_area)
        translations_progress.configure(
            length=400, orient="horizontal", mode="determinate", maximum=100
        )
        translations_progress.pack(fill="x", padx=5, pady=(0, 5))

        tkinter.Label(
            waiting_area, anchor="w", justify="left", wraplength=400,
            text="Paketler indirilip seçeneklerinize göre yerleştirilecek.\n"
                 "İnternet bağlantınıza göre biraz uzun sürebilir, lütfen sabırla bekleyiniz."
        ).pack(fill="x", padx=5, pady=15)

        def apply_operations():
            self.event_loop.run_until_complete(self.apply_operations(oneloader_progress, translations_progress))
            waiting_area.destroy()
            self.react_env_to_steam_dir(self.steam_dir)

        threading.Thread(target=apply_operations).start()

    async def apply_operations(self, loader_bar, tl_bar):
        LOG.info("Applying operations...")

        def download_report_hook(progressbar, count, block_size, total_size):
            progress = count * block_size
            percent = progress * 100 / total_size
            progressbar["value"] = percent
            progressbar.master.update()

        if self.candidate_packages.translations.manifest is None:
            self.show_alert_message_modal(
                message="Çeviri yükleme manifestosu çevrimiçi olarak alınamadığı için yükleme işlemi yapılamaz."
            )
            return

        try:
            if self.will_install_oneloader:
                LOG.info("Installing OneLoader...")

                def oneloader_download_report_hook(*args):
                    download_report_hook(loader_bar, *args)

                self.candidate_packages.oneloader.manifest.install(
                    game_dir=self.game_dir,
                    report_hook=oneloader_download_report_hook
                )

            if self.installed_packages.translations.found:
                LOG.info("Uninstalling translations...")
                clear_tl(game_dir=self.game_dir)

            LOG.info("Installing translations...")

            def translations_download_report_hook(*args):
                download_report_hook(tl_bar, *args)

            self.candidate_packages.translations.manifest.install(
                game_dir=self.game_dir,
                report_hook=translations_download_report_hook
            )
        except tkinter.TclError:
            self.show_alert_message_modal(
                "OMORI Türkçe Yama yükleme işlemini iptal ettiniz.\n"
                "Gerekli oyun dosyaları hasar görmüş olabilir.\n"
                "Steam'deki \"Oyun dosyalarının bütünlüğünü doğrula\" işlemini uygulamanız önerilir.",
                wraplength=750
            )
        except Exception:
            self.show_traceback_window()
            return
        else:
            self.show_alert_message_modal("OMORI Türkçe Yama yükleme işlemi hatasızca tamamlanmıştır.")

    def show_traceback_window(self):
        exc_type, exc_value, exc_traceback = sys.exc_info()
        formatted_exception = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        LOG.critical(formatted_exception)

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

        about_text = (
            f"OMORI Türkçe Yama yükleyicisi\n"
            f"https://omori-turkce.com/indir\n\n"
            f"{VERSION_TEXT}\n\n{LICENSE_TEXT}"
        )

        tkinter.Label(
            about_window, anchor="w", justify="left", wraplength=400, text=about_text
        ).pack(fill="x", padx=(55, 15), pady=20)

    async def request_and_react_to_manifest(self):
        try:
            manifest = requests.get(MANIFEST_URL).json()
        except Exception as e:
            self.show_alert_message_modal(f"Yama yükleme manifestosu internetten alınırken bir hata oluştu.\n\n{e}")
            return

        if manifest["manifestVersion"] != 1:
            self.show_alert_message_modal(
                message="Devam etmek için bu yükleme programını güncellemeniz gerekiyor.",
                title="Hata Raporlayıcı",
                button_text="İndirme sayfasına git",
                button_kwargs={"command": lambda: wopen(ONLINE_DOWNLOAD_PAGE)}
            )
            return

        index = {name: PackageState(version=data["version"], manifest=PackageManifest(name=name, **data))
                 for name, data in manifest["packages"].items()}
        self.candidate_packages = PackageIndex(**index)

        LOG.debug(f"{manifest = }")
        LOG.debug(f"{self.candidate_packages = }")

        self.apply_button.config(state="normal")

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

        label = tkinter.Label(alert, anchor="w", justify="left", wraplength=wraplength, text=message, **label_kwargs)
        label.pack(fill="x", padx=15, pady=15, **label_pack_kwargs)

        button_kwargs = {"text": button_text, "command": alert.destroy, **button_kwargs}
        button_pack_kwargs = {"ipadx": 15, "padx": 15, "pady": (5, 15), **button_pack_kwargs}

        button = tkinter.Button(alert, **button_kwargs)
        button.pack(**button_pack_kwargs)

        return [alert, label, button]

    def refresh(self):
        self.apply_button.config(state="disabled")

        async def _refresh():
            await self.request_and_react_to_manifest()
            self.react_env_to_steam_dir(self.steam_dir)

        threading.Thread(
            target=lambda: self.event_loop.run_until_complete(_refresh())
        ).start()


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


LICENSE_TEXT = """Copyright 2021-2023 Emre Özcan

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""


VERSION_CODE = "17"
VERSION_TEXT = f"Sürüm {VERSION_CODE}"
MANIFEST_URL = "https://omoritr.emreis.com/packages/v1_manifest.json"

ONLINE_DOWNLOAD_PAGE = "https://omoritr.emreis.com/download_page"
ONLINE_WEBSITE = "https://omoritr.emreis.com/website"
ONLINE_CREDITS = "https://omoritr.emreis.com/credits"

IS_RUNNING_FROZEN = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")
RUNNING_FILE_PATH = Path(__file__) if not IS_RUNNING_FROZEN else Path(sys.executable)

if __name__ == '__main__':
    LOG_FILE = RUNNING_FILE_PATH.parent / "omoritr-installer.log"
    LOG_HANDLER = logging.handlers.RotatingFileHandler(
        filename=LOG_FILE,
        encoding="utf-8",
        backupCount=1,
        maxBytes=5000
    )
    LOG_HANDLER.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOG_HANDLER.setLevel(logging.DEBUG)

    LOG = logging.getLogger("root")
    LOG.setLevel(logging.DEBUG)
    LOG.addHandler(LOG_HANDLER)

    logging.info(f"Starting omoritr-installer {VERSION_CODE}")
    logging.info(LICENSE_TEXT)
    logging.info("https://omori-turkce.com")
    logging.info("https://emreis.com")

    BUNDLE_DIR = Path(__file__).parent
    ICON_PATH = BUNDLE_DIR / "res/transparent-256.ico"

    LOG.debug(f"{IS_RUNNING_FROZEN = }")
    LOG.debug(f"{RUNNING_FILE_PATH = }")
    LOG.debug(f"{LOG_FILE = }")
    LOG.debug(f"{BUNDLE_DIR = }")

    ASYNC_LOOP = asyncio.new_event_loop()
    asyncio.set_event_loop(ASYNC_LOOP)

    main(ASYNC_LOOP)
