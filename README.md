# omoritr-installer

OMORI Türkçe Çeviri Ekibi tarafından hazırlanan otomatik OMORI mod kurulum
programı.

Program çalıştırılmaya hazır şekilde [sitemizin indirme sayfasından][dl] veya
kaynak kodu formatında git üzerinden GitHub'dan indirilebilir:

```sh
$ git clone git@github.com:omori-turkce/omoritr-installer.git
```

Sitede dağıtılan .exe dosyası oluşturulmak için `pyinstaller` kullanılmıştır.

```sh
$ python -m pip install --upgrade pip pyinstaller
$ pyinstaller omoritr-installer.spec
```

Yıllar boyu süren desteğiniz için teşekkürler.

[dl]: https://omori-turkce.com/indir
