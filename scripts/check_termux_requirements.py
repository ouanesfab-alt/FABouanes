#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de vérification des prérequis Termux pour FABouanes.
Vérifie la présence du toolchain C/Rust (clang, make, pkg-config, rustc, libffi, openssl)
nécessaire pour la compilation de packages natifs (asyncpg, pydantic-core, cryptography...).
"""
from __future__ import annotations

import os
import sys
import shutil
import subprocess
from typing import Dict, List, Tuple


REQUIRED_COMMANDS = {
    "clang": "clang",
    "make": "make",
    "pkg-config": "pkg-config",
    "rustc": "rust",
}

REQUIRED_LIBS = [
    "libffi",
    "openssl",
]


def is_termux_environment() -> bool:
    """Détecte si l'exécution se déroule dans l'environnement Termux (ou forcé via env/cli)."""
    if os.environ.get("FORCE_TERMUX_CHECK") == "1":
        return True
    if "TERMUX_VERSION" in os.environ:
        return True
    prefix = os.environ.get("PREFIX", "")
    if prefix.startswith("/data/data/com.termux"):
        return True
    if os.path.exists("/data/data/com.termux"):
        return True
    return False


def check_command(cmd: str) -> bool:
    """Vérifie si une commande/exécutable est disponible dans le PATH."""
    return shutil.which(cmd) is not None


def check_lib_with_pkg_config(lib_name: str) -> bool:
    """Vérifie si une bibliothèque est installée via pkg-config ou fichiers d'en-tête en fallback."""
    if check_command("pkg-config"):
        try:
            res = subprocess.run(
                ["pkg-config", "--exists", lib_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass

    # Fallback inspection dans les répertoires d'en-têtes et libs Termux / Unix
    prefix = os.environ.get("PREFIX", "/usr")
    inc_dir = os.path.join(prefix, "include")
    lib_dir = os.path.join(prefix, "lib")

    if lib_name == "libffi":
        has_header = os.path.exists(os.path.join(inc_dir, "ffi.h")) or os.path.exists(os.path.join(inc_dir, "ffitarget.h"))
        has_lib = any("libffi" in f for f in os.listdir(lib_dir)) if os.path.exists(lib_dir) else False
        return has_header or has_lib
    elif lib_name == "openssl":
        has_header = os.path.exists(os.path.join(inc_dir, "openssl"))
        has_lib = any("libssl" in f or "libcrypto" in f for f in os.listdir(lib_dir)) if os.path.exists(lib_dir) else False
        return has_header or has_lib

    return False


def run_requirements_check(verbose: bool = True) -> Tuple[bool, List[str]]:
    """
    Exécute la vérification complète des dépendances Termux.
    Retourne (succès: bool, liste_des_manquants: List[str]).
    """
    missing: List[str] = []

    # Vérification des exécutables
    for cmd, pkg in REQUIRED_COMMANDS.items():
        if not check_command(cmd):
            missing.append(pkg)
            if verbose:
                print(f"  ❌ Commande manquante: {cmd} (Paquet suggéré: {pkg})")
        elif verbose:
            print(f"  ✅ Commande détectée: {cmd}")

    # Vérification des bibliothèques C
    for lib in REQUIRED_LIBS:
        if not check_lib_with_pkg_config(lib):
            pkg_name = f"{lib}-dev" if not lib.endswith("-dev") else lib
            if lib == "libffi":
                pkg_name = "libffi"
            elif lib == "openssl":
                pkg_name = "openssl"
            if pkg_name not in missing:
                missing.append(pkg_name)
            if verbose:
                print(f"  ❌ Bibliothèque C manquante: {lib} (Paquet suggéré: {pkg_name})")
        elif verbose:
            print(f"  ✅ Bibliothèque C détectée: {lib}")

    success = len(missing) == 0
    return success, missing


def main() -> int:
    """Point d'entrée CLI du script."""
    is_termux = is_termux_environment()
    
    if "--quiet" not in sys.argv:
        print("🔍 Verification des prerequis de compilation Termux / ARM64...")

    if not is_termux and "--force" not in sys.argv:
        if "--quiet" not in sys.argv:
            print("ℹ️ Environnement hors-Termux détecté. Les vérifications manuelles C/Rust sont ignorées.")
        return 0

    success, missing = run_requirements_check(verbose="--quiet" not in sys.argv)

    if not success:
        print("\n=======================================================")
        print("⚠️ DÉPENDANCES MANQUANTES DÉTECTÉES SUR TERMUX")
        print("Pour compiler asyncpg, pydantic-core, cryptography & bcrypt,")
        print("veuillez exécuter la commande suivante dans Termux :")
        print("-------------------------------------------------------")
        pkgs_str = " ".join(sorted(set(missing)))
        print(f"pkg install {pkgs_str} -y")
        print("=======================================================\n")
        return 1

    if "--quiet" not in sys.argv:
        print("🎉 Tous les prérequis de compilation Termux sont installés et valides !")
    return 0


if __name__ == "__main__":
    sys.exit(main())
