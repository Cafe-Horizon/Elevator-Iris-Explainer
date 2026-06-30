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

def run_manim(scene_id, scene_info, quality):
    cmd = [
        sys.executable,
        "-m",
        "manim",
        f"-q{quality}",
        scene_info["file"],
        scene_info["class"]
    ]
    
    print(f"==> [Start] {scene_info['class']} (Scene {scene_id})")
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            stdin=subprocess.DEVNULL
        )
        return True, scene_id, scene_info["class"], result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, scene_id, scene_info["class"], e.stdout, e.stderr

def main():
    parser = argparse.ArgumentParser(description="Render Manim scenes in parallel.")
    parser.add_argument("-q", "--quality", default="l", choices=["l", "m", "h", "k"],
                        help="Render quality: l(low), m(medium), h(high), k(4k)")
    parser.add_argument("-s", "--scene", nargs="*", default=[],
                        help="Scene IDs to render (e.g. 04 or 01 02). If empty, renders all.")
    parser.add_argument("-j", "--jobs", type=int, default=0,
                        help="Number of concurrent rendering processes. Default is CPU count.")
    
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
            executor.submit(run_manim, sid, info, args.quality): sid 
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
    if failed_tasks:
        print(f"Failed scenes: {', '.join(failed_tasks)}", file=sys.stderr)
        sys.exit(1)
    else:
        print("All scenes rendered successfully. Output is under ./media/videos/")
        sys.exit(0)

if __name__ == "__main__":
    main()
