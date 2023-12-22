# omoritr-installer

OMORI Türkçe Çeviri Ekibi tarafından hazırlanan otomatik OMORI mod kurulum
programı.

# İndirme

Program çalıştırılmaya hazır şekilde [sitemizin indirme sayfasından][dl] veya
kaynak kodu formatında git üzerinden GitHub'dan indirilebilir:

```sh
$ git clone git@github.com:omori-turkce/omoritr-installer.git
```

# Gereksinimler

Çalıştırılabilir dosya için bir gereksinim yoktur ama Python kodunu çalıştırmak
veya çalıştırılabilir dosya yapmak için Python 3.11 veya daha üstü bir sürüm ve
`requests` kütüphanesinin yüklü olması gereklidir.

Bilgisayarınızda python ve pip yüklü ise aşağıdaki komut ile gereksinimleri
yükleyebilirsiniz:

```sh
$ python -m pip install --upgrade pip requests
```

Sitede dağıtılan .exe dosyası oluşturulmak için `pyinstaller` kullanılmıştır.

```sh
$ python -m pip install --upgrade pip pyinstaller
$ pyinstaller omoritr-installer.spec
```

Yıllar boyu süren desteğiniz için teşekkürler.

[dl]: https://omori-turkce.com/indir
