#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

SCENES = {
    "scene": {"file": "scenes/scene.py", "class": "RotateAboutPivot"},
    "01": {"file": "scenes/scene.py", "class": "Act1"},
    "02": {"file": "scenes/scene.py", "class": "Act2"},
    "03": {"file": "scenes/scene.py", "class": "Act3"},
    "04": {"file": "scenes/scene.py", "class": "Act4"},
    "05": {"file": "scenes/scene.py", "class": "Act5"},
    "06": {"file": "scenes/scene.py", "class": "Act6"},
    "07": {"file": "scenes/scene.py", "class": "Act7"},
    "08": {"file": "scenes/scene.py", "class": "Act8"},
    "09": {"file": "scenes/scene.py", "class": "Act9"},
}

QUALITY_MAP = {
    "l": "480p15",
    "m": "720p30",
    "h": "1080p60",
    "k": "2160p60",
}

def setup_latex_path():
    if shutil.which("latex") is None:
        user_profile = os.environ.get("USERPROFILE", "")
        miktex_path = os.path.join(user_profile, r"scoop\apps\latex\current\texmfs\install\miktex\bin\x64")
        if os.path.exists(miktex_path):
            os.environ["PATH"] = os.environ["PATH"] + os.pathsep + miktex_path
            if shutil.which("latex") is None:
                print("Warning: 'latex' command not found even after appending scoop path.", file=sys.stderr)
        else:
            print("Warning: 'latex' command not found in PATH.", file=sys.stderr)

def run_manim(scene_id, scene_info, quality, capture_output=True):
    cmd = [
        sys.executable,
        "-m",
        "manim",
        f"-q{quality}",
        scene_info["file"],
        scene_info["class"]
    ]
    
    print(f"==> [Start] {scene_info['class']} (Scene {scene_id})")
    
    stdout_dest = subprocess.PIPE if capture_output else None
    stderr_dest = subprocess.PIPE if capture_output else None
    
    try:
        result = subprocess.run(
            cmd,
            stdout=stdout_dest,
            stderr=stderr_dest,
            text=True,
            check=True,
            stdin=subprocess.DEVNULL
        )
        return True, scene_id, scene_info["class"], (result.stdout or ""), (result.stderr or "")
    except subprocess.CalledProcessError as e:
        return False, scene_id, scene_info["class"], (e.stdout or ""), (e.stderr or "")

def combine_videos(tasks, quality, output_name="combined.mp4"):
    quality_dir = QUALITY_MAP.get(quality, "480p15")
    base_dir = os.path.join("media", "videos", "scene", quality_dir)
    
    if not os.path.exists(base_dir):
        print(f"Warning: Directory '{base_dir}' does not exist. Skipping video combination.", file=sys.stderr)
        return False

    valid_files = []
    for _, info in tasks:
        file_path = os.path.join(base_dir, f"{info['class']}.mp4")
        if os.path.isfile(file_path):
            valid_files.append(f"{info['class']}.mp4")
        else:
            print(f"Warning: Expected scene file '{file_path}' not found for combination.", file=sys.stderr)

    if not valid_files:
        print("Error: No valid scene MP4 files found to combine.", file=sys.stderr)
        return False

    list_file_path = os.path.join(base_dir, "concat_list.txt")
    output_file_path = os.path.join(base_dir, output_name)

    try:
        with open(list_file_path, "w", encoding="utf-8") as f:
            for fname in valid_files:
                f.write(f"file '{fname}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file_path,
            "-c", "copy",
            output_file_path
        ]
        
        print(f"==> [Combine] Concatenating {len(valid_files)} video(s) into {output_file_path}")
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"==> [Combine SUCCESS] Output combined video: {output_file_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error during video combination: {e.stderr}", file=sys.stderr)
        return False
    finally:
        if os.path.exists(list_file_path):
            os.remove(list_file_path)

def main():
    parser = argparse.ArgumentParser(description="Render Manim scenes in parallel.")
    parser.add_argument("-q", "--quality", default="l", choices=["l", "m", "h", "k"],
                        help="Render quality: l(low), m(medium), h(high), k(4k)")
    parser.add_argument("-s", "--scene", nargs="*", default=[],
                        help="Scene IDs to render (e.g. 04 or scene). If empty, renders all.")
    parser.add_argument("-j", "--jobs", type=int, default=0,
                        help="Number of concurrent rendering processes. Default is CPU count.")
    parser.add_argument("--no-combine", action="store_true",
                        help="Disable automatic combination of rendered MP4 files into a single video.")
    
    args = parser.parse_args()
    
    setup_latex_path()
    
    # Identify target scenes
    target_ids = args.scene if args.scene else sorted(SCENES.keys())
    tasks = []
    for sid in target_ids:
        if sid in SCENES:
            tasks.append((sid, SCENES[sid]))
        elif sid.isdigit() and f"{int(sid):02d}" in SCENES:
            sid_norm = f"{int(sid):02d}"
            tasks.append((sid_norm, SCENES[sid_norm]))
        else:
            print(f"Warning: Unknown scene ID '{sid}'. Skipping.", file=sys.stderr)
            
    if not tasks:
        print("Error: No valid scenes selected to render.", file=sys.stderr)
        sys.exit(1)
        
    # Configure concurrency
    max_workers = args.jobs if args.jobs > 0 else multiprocessing.cpu_count()
    max_workers = min(max_workers, len(tasks))
    
    print(f"Parallel rendering started (Jobs: {max_workers}, Quality: -q{args.quality})")
    print(f"Scenes to render: {', '.join([t[1]['class'] for t in tasks])}")
    print("-" * 60)
    
    success_count = 0
    failed_tasks = []
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_manim, sid, info, args.quality, capture_output=(max_workers > 1)): sid 
            for sid, info in tasks
        }
        
        for future in as_completed(futures):
            success, sid, sclass, stdout, stderr = future.result()
            if success:
                print(f"==> [SUCCESS] {sclass} (Scene {sid}) completed successfully.")
                success_count += 1
            else:
                print(f"==> [FAILED] {sclass} (Scene {sid}) failed. Error output below:")
                print(stderr)
                print(stdout)
                print("-" * 60)
                failed_tasks.append(sclass)
                
    print("-" * 60)
    print(f"Done. Successfully rendered: {success_count}/{len(tasks)}")

    if not args.no_combine and success_count > 0:
        combine_videos(tasks, args.quality)

    if failed_tasks:
        print(f"Failed scenes: {', '.join(failed_tasks)}", file=sys.stderr)
        sys.exit(1)
    else:
        print("All scenes rendered successfully. Output is under ./media/videos/")
        sys.exit(0)

if __name__ == "__main__":
    main()
