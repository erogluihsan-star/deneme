#!/usr/bin/env python3
"""Proje klasorunu "kod (Git)" ve "agir dosya (Drive)" olarak ayirir.

Kullanim (Mac, proje klasorunun icinde veya yolunu vererek):
    python3 ayir.py ~/Desktop/avize --dry-run          # once sadece listeler
    python3 ayir.py ~/Desktop/avize                    # gercekten tasir
    python3 ayir.py ~/Desktop/avize --hedef "~/Library/CloudStorage/GoogleDrive-.../avize-dosyalar"
    python3 ayir.py ~/Desktop/avize --esik-mb 10 --push

Ne yapar:
  1. Agir dosyalari bulur (boyut esigi ustu VEYA agir uzanti).
  2. Bunlari --hedef klasorune ayni alt klasor yapisiyla TASIR
     (hedef varsayilan: proje klasorunun yaninda "<proje>-drive").
  3. Her tasimayi hedef/manifest.txt'ye yazar (geri almak icin --geri-al).
  4. Proje icinde .gitignore ve DOSYALAR.md olusturur.
  5. --push verilirse git init/add/commit/push yapar.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

AGIR_UZANTILAR = {
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".psd", ".exr", ".hdr",
    ".mp4", ".mov", ".avi", ".mkv",
    ".obj", ".fbx", ".stl", ".blend", ".3ds", ".dae", ".glb", ".gltf",
    ".step", ".stp", ".iges", ".igs", ".dwg", ".dxf", ".3dm", ".skp",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".dmg", ".iso",
    ".pdf", ".xlsx", ".csv", ".npy", ".npz", ".pkl", ".h5", ".bin", ".db", ".sqlite",
}
YOK_SAY = {".git", "node_modules", "__pycache__", ".venv", "venv", ".DS_Store"}
# Bunlar Drive'a tasinmaz, sadece .gitignore'a eklenir (silinebilir/uretilebilir).
URETILEBILIR = ["node_modules/", "__pycache__/", "*.pyc", ".venv/", "venv/",
                "dist/", "build/", ".DS_Store"]


def mb(n):
    return f"{n / 1024 / 1024:.1f} MB"


def tara(kok: Path, esik_bayt: int):
    agir = []
    for yol, klasorler, dosyalar in os.walk(kok):
        klasorler[:] = [d for d in klasorler if d not in YOK_SAY]
        for ad in dosyalar:
            if ad in YOK_SAY:
                continue
            p = Path(yol) / ad
            if p.is_symlink():
                continue
            boyut = p.stat().st_size
            if boyut >= esik_bayt or p.suffix.lower() in AGIR_UZANTILAR:
                agir.append((p, boyut))
    return agir


def geri_al(kok: Path, hedef: Path):
    mani = hedef / "manifest.txt"
    if not mani.exists():
        sys.exit(f"Manifest yok: {mani}")
    for satir in mani.read_text().splitlines():
        if not satir.strip():
            continue
        rel = satir.split("\t")[0]
        kaynak, dest = hedef / rel, kok / rel
        if kaynak.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(kaynak), str(dest))
            print("geri alindi:", rel)


def git(kok, *args):
    subprocess.run(["git", *args], cwd=kok, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proje", help="Proje klasoru")
    ap.add_argument("--hedef", help="Agir dosyalarin tasinacagi klasor (orn. Drive senkron klasoru)")
    ap.add_argument("--esik-mb", type=float, default=5, help="Bu boyut ve ustu agir sayilir (varsayilan 5)")
    ap.add_argument("--dry-run", action="store_true", help="Hicbir sey tasimadan listele")
    ap.add_argument("--push", action="store_true", help="Sonunda git add/commit/push yap")
    ap.add_argument("--geri-al", action="store_true", help="Manifest'e gore dosyalari geri tasi")
    a = ap.parse_args()

    kok = Path(a.proje).expanduser().resolve()
    if not kok.is_dir():
        sys.exit(f"Klasor yok: {kok}")
    hedef = Path(a.hedef).expanduser().resolve() if a.hedef else kok.parent / f"{kok.name}-drive"
    if hedef == kok or kok in hedef.parents:
        sys.exit("Hedef, proje klasorunun icinde olamaz.")

    if a.geri_al:
        return geri_al(kok, hedef)

    agir = tara(kok, int(a.esik_mb * 1024 * 1024))
    toplam = sum(b for _, b in agir)
    print(f"Proje : {kok}\nHedef : {hedef}")
    print(f"{len(agir)} agir dosya, toplam {mb(toplam)} (esik {a.esik_mb} MB veya agir uzanti)\n")
    for p, b in sorted(agir, key=lambda x: -x[1])[:40]:
        print(f"  {mb(b):>10}  {p.relative_to(kok)}")
    if len(agir) > 40:
        print(f"  ... ve {len(agir) - 40} dosya daha")

    if a.dry_run:
        print("\n[dry-run] Hicbir sey tasinmadi. Uygun gorunuyorsa --dry-run olmadan tekrar calistirin.")
        return

    hedef.mkdir(parents=True, exist_ok=True)
    satirlar = []
    for p, b in agir:
        rel = p.relative_to(kok)
        dest = hedef / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            print("atlandi (hedefte var):", rel)
            continue
        shutil.move(str(p), str(dest))
        satirlar.append(f"{rel}\t{b}")
    with open(hedef / "manifest.txt", "a") as f:
        f.write("\n".join(satirlar) + ("\n" if satirlar else ""))

    # .gitignore
    gi = kok / ".gitignore"
    mevcut = gi.read_text().splitlines() if gi.exists() else []
    eklenecek = [s for s in URETILEBILIR if s not in mevcut]
    uzantilar = [f"*{u}" for u in sorted(AGIR_UZANTILAR) if f"*{u}" not in mevcut]
    with open(gi, "a") as f:
        if eklenecek or uzantilar:
            f.write("\n# ayir.py: agir dosyalar Drive'da\n")
            f.write("\n".join(eklenecek + uzantilar) + "\n")

    # DOSYALAR.md
    (kok / "DOSYALAR.md").write_text(
        "# Agir dosyalar\n\n"
        "Bu repoda yalnizca kod ve hafif dosyalar var. Agir dosyalar Google Drive'da:\n\n"
        "- Drive klasoru: **(buraya link ekleyin)**\n"
        "- Ayni klasor yapisiyla proje kokune kopyalayin.\n"
        f"- Tasinan dosya listesi: `manifest.txt` ({len(satirlar)} dosya, {mb(toplam)})\n"
    )
    print(f"\nTasindi: {len(satirlar)} dosya -> {hedef}\nManifest: {hedef / 'manifest.txt'}")
    print("Geri almak icin: python3 ayir.py <proje> --hedef <hedef> --geri-al")

    if a.push:
        if not (kok / ".git").exists():
            git(kok, "init", "-b", "main")
        git(kok, "add", ".")
        git(kok, "commit", "-m", "Kod ve hafif dosyalar; agir dosyalar Drive'a tasindi")
        r = subprocess.run(["git", "remote"], cwd=kok, capture_output=True, text=True)
        if "origin" in r.stdout.split():
            git(kok, "push", "-u", "origin", "HEAD")
        else:
            print("\nremote (origin) tanimli degil. Once:\n"
                  "  git remote add origin https://github.com/erogluihsan-star/avize.git\n"
                  "  git push -u origin main")


if __name__ == "__main__":
    main()
