"""Worker: PostgreSQL backup with optional encryption and offsite upload."""
import logging
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("/mnt/HC_Volume_104764377/backups/lorcana")
RETAIN_DAYS = 7
DB_NAME = "lorcana"


def run_backup(encrypt: bool = False, upload: bool = False) -> str:
    """Run pg_dump, optionally encrypt and upload offsite."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    dump_path = BACKUP_DIR / f"pg_{ts}.dump"

    # 1. pg_dump
    logger.info("Starting pg_dump to %s", dump_path)
    result = subprocess.run(
        ["pg_dump", "-Fc", "-Z6", DB_NAME, "-f", str(dump_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.error("pg_dump failed: %s", result.stderr)
        return f"FAIL: {result.stderr}"

    size_mb = dump_path.stat().st_size / (1024 * 1024)
    logger.info("Dump created: %.1f MB", size_mb)

    # 2. Optional GPG encryption
    final_path = dump_path
    passphrase_file = Path("/root/.backup_passphrase")
    if encrypt and passphrase_file.exists():
        enc_result = subprocess.run(
            ["gpg", "--batch", "--symmetric", "--cipher-algo", "AES256",
             "--passphrase-file", str(passphrase_file), str(dump_path)],
            capture_output=True, text=True,
        )
        if enc_result.returncode == 0:
            dump_path.unlink()
            final_path = dump_path.with_suffix(".dump.gpg")
            logger.info("Encrypted: %s", final_path.name)
        else:
            logger.warning("Encryption failed, keeping unencrypted: %s", enc_result.stderr)

    # 3. Optional offsite upload (placeholder)
    if upload:
        logger.info("Offsite upload not configured — skipping")

    # 4. Cleanup old backups
    _cleanup_old(BACKUP_DIR)

    return f"OK: {final_path.name} ({size_mb:.1f} MB)"


def _cleanup_old(backup_dir: Path):
    """Remove backups older than RETAIN_DAYS."""
    import time
    cutoff = time.time() - (RETAIN_DAYS * 86400)
    for f in backup_dir.glob("pg_*"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            logger.info("Removed old backup: %s", f.name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    msg = run_backup()
    print(msg)
