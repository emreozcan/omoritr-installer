import json
import os.path
import shutil
import sys
import tkinter
import traceback
import winreg
import zipfile
from glob import glob
from pathlib import Path
from typing import Union


def get_steam_path() -> Path:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "SOFTWARE\\Valve\\Steam") as key:
        return Path(winreg.QueryValueEx(key, "SteamPath")[0])


def is_omori_installed(steampath: Path) -> bool:
    return (steampath / "steamapps/common/OMORI/OMORI.exe").exists()


def is_gomori_installed(steampath: Path) -> bool:
    return (steampath / "steamapps/common/OMORI/www/gomori/gomori.js").exists()


def is_plutofix_installed(steampath: Path) -> bool:
    return "data_pluto" in \
           (steampath / "steamapps/common/OMORI/www/gomori/constants/filetypes.js").read_text(encoding="utf-8")


def are_translations_installed(steampath: Path) -> bool:
    return (steampath / "steamapps/common/OMORI/www/mods/omoritr/mod.json").exists()


def get_translation_version(steampath: Path) -> str:
    return json.loads(
        (steampath / "steamapps/common/OMORI/www/mods/omoritr/mod.json").read_text(encoding="utf-8")
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


def safe_delete(container: Union[Path, str], paths: list[Union[Path, str]]) -> None:
    real_container_path = os.path.realpath(container)
    for target_path in paths:
        real_target_path = os.path.realpath(target_path)
        if not os.path.exists(real_target_path):
            continue
        if not real_target_path.startswith(real_container_path):
            continue
        if os.path.isdir(real_target_path):
            shutil.rmtree(real_target_path)
        else:
            os.remove(real_target_path)


def clear_gomori(game_dir: Path) -> None:
    names = ["www/JSON-Patch*", "www/adm-zip*", "www/gomori", "www/index.html"]
    gomori_dirs = []
    for name in names:
        gomori_dirs.extend(glob(str(game_dir / name)))
    safe_delete(game_dir, gomori_dirs)


def clear_tl(game_dir: Path) -> None:
    tl_path = game_dir / "www/mods/omoritr"
    if tl_path.exists():
        safe_delete(game_dir, [tl_path])


def main():
    bundle_dir = Path(__file__).parent
    gomori_archive_path = Path.cwd() / bundle_dir / "res/gomori.zip"
    translation_archive_path = Path.cwd() / bundle_dir / "res/omoritr.zip"
    icon_path = Path.cwd() / bundle_dir / "res/transparent-256.ico"

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
        pass

    steam_info_label = tkinter.Label(root, justify="left", anchor="w")
    steam_info_label.pack(fill="x", padx=5, pady=5)
    if not (steam_dir is not None and is_omori_installed(steam_dir)):
        steam_info_label.config(
            text="Bilgisayarınızda OMORI tespit edilememiştir.\n"
                 "Lütfen bilgisayarınıza OMORI yükleyip bu programı tekrar çalıştırın.",
            fg="#FF0000"
        )
        root.mainloop()
        sys.exit(1)

    gomori_installed = is_gomori_installed(steampath=steam_dir)
    plutofix_installed = is_plutofix_installed(steampath=steam_dir) if gomori_installed else False
    gomori_install_required = not gomori_installed or not plutofix_installed

    tl_installed = are_translations_installed(steampath=steam_dir)
    tl_version = get_translation_version(steampath=steam_dir) if tl_installed else None

    steam_info_label.config(
        text="OMORI bilgisayarınızda otomatik olarak tespit edilmiştir.\n"
             "Bilgileri inceleyip düğmeye tıklayarak yamayı yükleyebilirsiniz."
    )

    game_dir = steam_dir.joinpath("steamapps/common/OMORI/")

    tkinter.Label(root, text="Oyun konumu:", justify="left", anchor="w") \
        .pack(fill="x", padx=5, pady=(5, 0))

    game_location_entry = tkinter.Entry(root, justify="left")
    game_location_entry.pack(fill="x", padx=5, pady=(0, 5))
    game_location_entry.insert(0, game_dir)
    game_location_entry.config(state="disabled")

    tkinter.Label(root, text="Yapılan kontroller:", justify="left", anchor="w") \
        .pack(fill="x", padx=5, pady=(5, 0))

    game_installed_checkbox = tkinter.Checkbutton(root, text="OMORI yüklenmiş", state="disabled", anchor="w")
    if is_omori_installed(steam_dir):
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
            text=f"Türkçe Yama değiştirilecek (yeni: {get_packed_tl_version(translation_archive_path)})"
        )
    else:
        to_install_tl_checkbox.config(
            text=f"Türkçe Yama yüklenecek ({get_packed_tl_version(translation_archive_path)})"
        )
    to_install_tl_checkbox.select()
    to_install_tl_checkbox.pack(fill="x", padx=5, pady=(0, 5))

    def apply_button_callback():
        action_button.config(state="disabled")
        try:
            if gomori_install_required:
                if gomori_installed:
                    clear_gomori(game_dir=game_dir)
                install_gomori(gomori_archive_path=gomori_archive_path, game_dir=game_dir)
            if tl_installed:
                clear_tl(game_dir=game_dir)
            install_translations(translation_archive_path=translation_archive_path, game_dir=game_dir)
        except Exception:
            alert = tkinter.Toplevel(root)
            alert.title("OMORI Türkçe Yama yükleyicisi")
            alert.iconbitmap(icon_path)
            alert.resizable(False, False)

            tkinter.Label(alert, text="OMORI Türkçe Yama yükleme işlemi sırasında beklenmeyen bir hata oluştu.") \
                .pack(fill="x", padx=5, pady=5)

            exc_type, exc_value, exc_traceback = sys.exc_info()
            formatted_exception = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

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
