import os
import pwd
import shutil

from . import shared_state
from .utils import run_command

def copy_config_files():
    shared_state.log.info("Copying configuration files...")
    pw_user_info = pwd.getpwnam(shared_state.TARGET_USER)
    
    # Zshrc
    if not shared_state.ZSHRC_SOURCE_PATH or not shared_state.ZSHRC_SOURCE_PATH.is_file():
        shared_state.log.error(f"Source .zshrc path not valid or file missing: {shared_state.ZSHRC_SOURCE_PATH}")
        return
        
    target_zshrc_path = shared_state.TARGET_USER_HOME / shared_state.ZSHRC_SOURCE_FILE_NAME
    shared_state.log.info(f"Copying [magenta]{shared_state.ZSHRC_SOURCE_FILE_NAME}[/] to [cyan]{target_zshrc_path}[/]")
    if target_zshrc_path.exists():
        backup_zshrc_path = shared_state.TARGET_USER_HOME / f".zshrc.bkp_nova_{os.urandom(4).hex()}"
        shared_state.log.warning(f"Backing up existing .zshrc to [cyan]{backup_zshrc_path}[/]")
        try: run_command(["cp",str(target_zshrc_path),str(backup_zshrc_path)],as_user=shared_state.TARGET_USER)
        except Exception: shutil.copy(target_zshrc_path, backup_zshrc_path)
    try:
        shutil.copy(shared_state.ZSHRC_SOURCE_PATH, target_zshrc_path)
        os.chown(target_zshrc_path, pw_user_info.pw_uid, pw_user_info.pw_gid)
        shared_state.log.info(f":floppy_disk: [magenta]{shared_state.ZSHRC_SOURCE_FILE_NAME}[/] copied.")
    except Exception as e_zshrc: shared_state.log.error(f"[bold red]Failed to copy .zshrc: {e_zshrc}[/]")

    # Nanorc
    if not shared_state.NANORC_SOURCE_PATH or not shared_state.NANORC_SOURCE_PATH.is_file():
        shared_state.log.error(f"Source .nanorc path not valid or file missing: {shared_state.NANORC_SOURCE_PATH}")
        return

    nanorc_config_dir = shared_state.TARGET_USER_HOME / ".config/nano"
    target_nanorc_path = nanorc_config_dir / shared_state.NANORC_SOURCE_FILE_NAME
    try: run_command(["mkdir","-p",str(nanorc_config_dir)],as_user=shared_state.TARGET_USER)
    except Exception as e_mkdir_nano:
        shared_state.log.error(f"Failed to create nano config dir {nanorc_config_dir}: {e_mkdir_nano}"); return

    shared_state.log.info(f"Copying [magenta]{shared_state.NANORC_SOURCE_FILE_NAME}[/] to [cyan]{target_nanorc_path}[/]")
    if target_nanorc_path.exists():
        backup_nanorc_path = nanorc_config_dir / f"nanorc.bkp_nova_{os.urandom(4).hex()}"
        shared_state.log.warning(f"Backing up existing nanorc to [cyan]{backup_nanorc_path}[/]")
        try: run_command(["cp",str(target_nanorc_path),str(backup_nanorc_path)],as_user=shared_state.TARGET_USER)
        except Exception: shutil.copy(target_nanorc_path, backup_nanorc_path)
    try:
        shutil.copy(shared_state.NANORC_SOURCE_PATH, target_nanorc_path)
        os.chown(target_nanorc_path, pw_user_info.pw_uid, pw_user_info.pw_gid)
        if nanorc_config_dir.stat().st_uid != pw_user_info.pw_uid: os.chown(nanorc_config_dir, pw_user_info.pw_uid, pw_user_info.pw_gid)
        if nanorc_config_dir.parent.name == ".config" and nanorc_config_dir.parent.stat().st_uid != pw_user_info.pw_uid:
            os.chown(nanorc_config_dir.parent, pw_user_info.pw_uid, pw_user_info.pw_gid)
        shared_state.log.info(f":floppy_disk: [magenta]{shared_state.NANORC_SOURCE_FILE_NAME}[/] copied to {nanorc_config_dir}.")
    except Exception as e_nanorc: shared_state.log.error(f"[bold red]Failed to copy nanorc: {e_nanorc}[/]")