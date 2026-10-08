import requests
import json
import csv
import os
import time
from datetime import datetime


# ============================================================
# AYARLAR
# ============================================================

GITHUB_TOKEN = "Buraya bir github token i ekleyin farklı bir mail oluşturup alabilirsiniz"

# Kaç farklı sayfa çekilecek?
MAX_PAGES = 10

# GitHub API sayfa başına maksimum 100 sonuç destekler.
PER_PAGE = 100

# API timeout
TIMEOUT = 20

# Hata durumunda kaç kez tekrar denenecek?
MAX_RETRIES = 3

# Her sorgu arasında bekleme
REQUEST_DELAY = 0.5

# CSV oluşturulsun mu?
CREATE_CSV = True

# JSON oluşturulsun mu?
CREATE_JSON = True


# ============================================================
# ARAMA SORGULARI
# ============================================================

ARAMALAR = [

    {
        "isim": "MongoDB bağlantıları",
        "query": '"mongodb://" extension:js'
    },

    {
        "isim": "API Key",
        "query": 'api_key extension:env'
    },

    {
        "isim": "Bearer Token",
        "query": '"Bearer " language:javascript'
    },

    # Buraya istediğin kadar ekleyebilirsin.

    # {
    #     "isim": "Özel arama",
    #     "query": '"deneme" extension:php'
    # },

]


# ============================================================
# HEADERS
# ============================================================

if not GITHUB_TOKEN:

    print()
    print("❌ GITHUB_TOKEN bulunamadı.")
    print()
    print("Windows CMD:")
    print('set GITHUB_TOKEN=github_tokenunuz')
    print()
    print("PowerShell:")
    print('$env:GITHUB_TOKEN="github_tokenunuz"')
    print()

    exit()


HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "GitHub-Search-Tool"
}


SEARCH_URL = "https://api.github.com/search/code"


# ============================================================
# DOSYA ADI
# ============================================================

def sonuc_dosyasi_bul(prefix, extension):

    sayi = 0

    while True:

        dosya_adi = f"{prefix}{sayi}.{extension}"

        if not os.path.exists(dosya_adi):
            return dosya_adi

        sayi += 1


# ============================================================
# RATE LIMIT
# ============================================================

def rate_limit_goster():

    url = "https://api.github.com/rate_limit"

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            return

        data = response.json()

        core = data.get("resources", {}).get("core", {})

        limit = core.get("limit", 0)
        remaining = core.get("remaining", 0)
        reset = core.get("reset", 0)

        print()
        print("==========================================")
        print(" GITHUB RATE LIMIT")
        print("==========================================")
        print(f"Limit     : {limit}")
        print(f"Kalan     : {remaining}")

        if reset:

            reset_time = datetime.fromtimestamp(reset)

            print(
                f"Sıfırlanma: "
                f"{reset_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        print("==========================================")

    except requests.RequestException:

        print("[UYARI] Rate limit bilgisi alınamadı.")


# ============================================================
# GITHUB CODE SEARCH
# ============================================================

def github_ara(query):

    tum_sonuclar = []

    for page in range(1, MAX_PAGES + 1):

        params = {
            "q": query,
            "per_page": PER_PAGE,
            "page": page
        }

        response = None

        # ------------------------------------------
        # RETRY
        # ------------------------------------------

        for deneme in range(1, MAX_RETRIES + 1):

            try:

                response = requests.get(
                    SEARCH_URL,
                    headers=HEADERS,
                    params=params,
                    timeout=TIMEOUT
                )

                break

            except requests.RequestException as hata:

                print(
                    f"[UYARI] Bağlantı hatası "
                    f"({deneme}/{MAX_RETRIES}): {hata}"
                )

                if deneme < MAX_RETRIES:

                    time.sleep(2 ** deneme)

        # ------------------------------------------
        # RESPONSE KONTROL
        # ------------------------------------------

        if response is None:
            break

        # Rate limit
        if response.status_code == 403:

            print()
            print("⚠️ GitHub API rate limit / erişim hatası.")
            print(response.text[:500])

            break

        # Geçersiz sorgu
        if response.status_code == 422:

            print()
            print("❌ GitHub sorgusu geçersiz.")
            print(f"Sorgu: {query}")
            print(response.text[:500])

            break

        # Diğer hatalar
        if response.status_code != 200:

            print(
                f"[HATA] HTTP {response.status_code}"
            )

            break

        # ------------------------------------------
        # JSON
        # ------------------------------------------

        try:

            data = response.json()

        except json.JSONDecodeError:

            print("[HATA] GitHub geçerli JSON döndürmedi.")

            break

        items = data.get("items", [])

        if not items:
            break

        tum_sonuclar.extend(items)

        print(
            f"      Sayfa {page}: "
            f"{len(items)} sonuç"
        )

        # GitHub toplam sonucu
        total_count = data.get(
            "total_count",
            len(tum_sonuclar)
        )

        # Toplamı aldıysak yeterli
        if len(tum_sonuclar) >= total_count:
            break

        # GitHub Code Search'in pratik sonuç sınırı
        if len(tum_sonuclar) >= 1000:
            break

        time.sleep(REQUEST_DELAY)

    return tum_sonuclar


# ============================================================
# SONUCU TEMİZLE
# ============================================================

def sonucu_temizle(sonuc, sorgu_adi, query):

    repository = sonuc.get(
        "repository",
        {}
    )

    repo_adi = repository.get(
        "full_name",
        ""
    )

    repo_url = repository.get(
        "html_url",
        ""
    )

    dosya_adi = sonuc.get(
        "name",
        ""
    )

    dosya_path = sonuc.get(
        "path",
        ""
    )

    github_url = sonuc.get(
        "html_url",
        ""
    )

    sha = sonuc.get(
        "sha",
        ""
    )

    return {

        "arama": sorgu_adi,

        "query": query,

        "repository": repo_adi,

        "repository_url": repo_url,

        "dosya": dosya_adi,

        "path": dosya_path,

        "url": github_url,

        "sha": sha

    }


# ============================================================
# DUPLICATE TEMİZLE
# ============================================================

def benzersiz_sonuclar(suanki_sonuclar):

    benzersiz = {}

    for sonuc in suanki_sonuclar:

        key = (
            sonuc.get("repository", ""),
            sonuc.get("path", ""),
            sonuc.get("sha", "")
        )

        if key not in benzersiz:

            benzersiz[key] = sonuc

    return list(benzersiz.values())


# ============================================================
# JSON KAYDET
# ============================================================

def json_kaydet(veri):

    dosya = sonuc_dosyasi_bul(
        "github_sonuclari",
        "json"
    )

    with open(
        dosya,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            veri,
            f,
            ensure_ascii=False,
            indent=4
        )

    return dosya


# ============================================================
# CSV KAYDET
# ============================================================

def csv_kaydet(veriler):

    dosya = sonuc_dosyasi_bul(
        "github_sonuclari",
        "csv"
    )

    if not veriler:
        return None

    alanlar = [

        "arama",
        "query",
        "repository",
        "repository_url",
        "dosya",
        "path",
        "url",
        "sha"

    ]

    with open(
        dosya,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=alanlar
        )

        writer.writeheader()

        writer.writerows(veriler)

    return dosya


# ============================================================
# ANA PROGRAM
# ============================================================

def main():

    print()
    print("==========================================")
    print("       GITHUB CODE SEARCH TOOL")
    print("==========================================")
    print()

    print(
        f"Toplam sorgu: {len(ARAMALAR)}"
    )

    print(
        f"Maksimum sayfa: {MAX_PAGES}"
    )

    print(
        f"Sayfa başına: {PER_PAGE}"
    )

    print()

    rate_limit_goster()

    tum_sonuclar = []

    istatistik = []

    # ========================================================
    # ARAMALAR
    # ========================================================

    for index, arama in enumerate(
        ARAMALAR,
        start=1
    ):

        isim = arama["isim"]
        query = arama["query"]

        print()
        print("==========================================")
        print(
            f"[{index}/{len(ARAMALAR)}] {isim}"
        )
        print("==========================================")

        print(
            f"🔎 Sorgu: {query}"
        )

        ham_sonuclar = github_ara(query)

        temiz_sonuclar = []

        for sonuc in ham_sonuclar:

            temiz = sonucu_temizle(
                sonuc,
                isim,
                query
            )

            temiz_sonuclar.append(temiz)

        # ------------------------------------------
        # BU SORGUDA DUPLICATE
        # ------------------------------------------

        temiz_sonuclar = benzersiz_sonuclar(
            temiz_sonuclar
        )

        tum_sonuclar.extend(
            temiz_sonuclar
        )

        istatistik.append({

            "arama": isim,

            "query": query,

            "sonuc": len(temiz_sonuclar)

        })

        print()
        print(
            f"📊 Benzersiz sonuç: "
            f"{len(temiz_sonuclar)}"
        )

    # ========================================================
    # TÜM SONUÇLARDA DUPLICATE
    # ========================================================

    print()
    print("==========================================")
    print(" DUPLICATE TEMİZLENİYOR")
    print("==========================================")

    toplam_once = len(tum_sonuclar)

    tum_sonuclar = benzersiz_sonuclar(
        tum_sonuclar
    )

    toplam_sonra = len(tum_sonuclar)

    print(
        f"Önce : {toplam_once}"
    )

    print(
        f"Sonra: {toplam_sonra}"
    )

    print(
        f"Silinen duplicate: "
        f"{toplam_once - toplam_sonra}"
    )

    # ========================================================
    # JSON VERİSİ
    # ========================================================

    cikti = {

        "metadata": {

            "olusturma_zamani":
                datetime.now().isoformat(),

            "toplam_arama":
                len(ARAMALAR),

            "toplam_benzersiz_sonuc":
                len(tum_sonuclar),

            "max_pages":
                MAX_PAGES,

            "per_page":
                PER_PAGE

        },

        "istatistik":
            istatistik,

        "sonuclar":
            tum_sonuclar

    }

    # ========================================================
    # JSON
    # ========================================================

    json_dosya = None

    if CREATE_JSON:

        json_dosya = json_kaydet(
            cikti
        )

        print()
        print(
            f"📄 JSON: {json_dosya}"
        )

    # ========================================================
    # CSV
    # ========================================================

    csv_dosya = None

    if CREATE_CSV:

        csv_dosya = csv_kaydet(
            tum_sonuclar
        )

        if csv_dosya:

            print(
                f"📊 CSV : {csv_dosya}"
            )

    # ========================================================
    # SONUÇ
    # ========================================================

    print()
    print("==========================================")
    print("           ARAMA TAMAMLANDI")
    print("==========================================")

    print(
        f"🔎 Sorgu sayısı : {len(ARAMALAR)}"
    )

    print(
        f"📁 Toplam sonuç : {len(tum_sonuclar)}"
    )

    if json_dosya:

        print(
            f"📄 JSON         : {json_dosya}"
        )

    if csv_dosya:

        print(
            f"📊 CSV          : {csv_dosya}"
        )

    print("==========================================")
    print()


# ============================================================
# PROGRAMI BAŞLAT
# ============================================================

if __name__ == "__main__":

    main()