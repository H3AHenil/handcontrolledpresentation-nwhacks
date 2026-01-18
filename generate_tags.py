"""
Generate printable AprilTag images (tag16h5 family).

30 tags available (IDs 0-29), supports up to 7 screens.

Corner tag assignment:
- ID 0: Top-left
- ID 1: Top-right
- ID 2: Bottom-right
- ID 3: Bottom-left
"""

from pathlib import Path

import cv2
import numpy as np

# tag16h5: 30 tags (IDs 0-29), max 7 screens
APRILTAG_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_16h5)
MAX_TAG_ID = 29
MAX_SCREENS = 7


def generate_apriltag(tag_id: int, size: int = 200) -> np.ndarray:
    """
    Generate a tag16h5 AprilTag image.
    
    Args:
        tag_id: Tag ID (0-29)
        size: Output image size in pixels
        
    Returns:
        Grayscale image of the tag
    """
    if not 0 <= tag_id <= MAX_TAG_ID:
        raise ValueError(f"Tag ID must be 0-{MAX_TAG_ID}, got {tag_id}")
    
    return cv2.aruco.generateImageMarker(APRILTAG_DICT, tag_id, size)


def generate_single_tag(
    tag_id: int,
    output_path: Path,
    size: int = 300,
    label: str | None = None,
) -> Path:
    """
    Generate a single AprilTag and save to file.
    
    Args:
        tag_id: Tag ID (0-29)
        output_path: Where to save the PNG
        size: Tag size in pixels (before margin)
        label: Optional label text below the tag
        
    Returns:
        Path to the saved file
    """
    img = generate_apriltag(tag_id, size)
    
    # Add white margin for easier cutting
    margin = 50
    bordered = np.ones((size + 2 * margin, size + 2 * margin), dtype=np.uint8) * 255
    bordered[margin:margin + size, margin:margin + size] = img
    
    # Add label
    label_text = label or f"ID {tag_id}"
    cv2.putText(
        bordered,
        label_text,
        (margin, size + margin + 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        0,
        2
    )
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), bordered)
    return output_path


def generate_tags(
    tag_ids: list[int],
    output_dir: Path,
    size: int = 300,
    labels: dict[int, str] | None = None,
) -> list[Path]:
    """
    Generate multiple AprilTags and save to files.
    
    Args:
        tag_ids: List of tag IDs to generate (0-29)
        output_dir: Directory to save tags
        size: Tag size in pixels
        labels: Optional dict mapping tag_id -> label text
        
    Returns:
        List of paths to generated files
    """
    output_dir = Path(output_dir)
    labels = labels or {}
    paths = []
    
    for tag_id in tag_ids:
        label = labels.get(tag_id, f"ID {tag_id}")
        filename = output_dir / f"tag_{tag_id}.png"
        generate_single_tag(tag_id, filename, size, label)
        print(f"Generated: {filename}")
        paths.append(filename)
    
    return paths


def generate_corner_tags(output_dir: Path, size: int = 300):
    """Generate the 4 default corner tags (IDs 0-3) for screen registration."""
    output_dir = Path(output_dir)
    
    corner_labels = {
        0: "ID 0 - Top Left",
        1: "ID 1 - Top Right",
        2: "ID 2 - Bottom Right",
        3: "ID 3 - Bottom Left",
    }
    corner_names = ["top_left", "top_right", "bottom_right", "bottom_left"]
    
    # Generate individual tags
    for tag_id in range(4):
        filename = output_dir / f"tag_{tag_id}_{corner_names[tag_id]}.png"
        generate_single_tag(tag_id, filename, size, corner_labels[tag_id])
        print(f"Generated: {filename}")
    
    # Create combined sheet for easy printing
    tags = [
        cv2.imread(str(output_dir / f"tag_{i}_{corner_names[i]}.png"))
        for i in range(4)
    ]
    
    # 2x2 grid layout matching screen corners
    row1 = np.hstack([tags[0], tags[1]])  # TL, TR
    row2 = np.hstack([tags[3], tags[2]])  # BL, BR
    combined = np.vstack([row1, row2])
    
    combined_path = output_dir / "all_tags_printable.png"
    cv2.imwrite(str(combined_path), combined)
    print(f"\nCombined printable sheet: {combined_path}")


def generate_multiscreen_tags(
    num_screens: int,
    output_dir: Path,
    size: int = 300,
    screen_names: list[str] | None = None,
):
    """
    Generate tags for multiple screens.
    
    Each screen gets 4 consecutive tag IDs:
      Screen 0: IDs 0-3
      Screen 1: IDs 4-7
      Screen 2: IDs 8-11
      etc.
    
    Args:
        num_screens: Number of screens/monitors (max 7)
        output_dir: Directory to save tags
        size: Tag size in pixels
        screen_names: Optional names for screens (e.g., ["Left", "Right"])
    """
    if num_screens > MAX_SCREENS:
        raise ValueError(f"Maximum {MAX_SCREENS} screens supported (30 tags / 4 per screen)")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    screen_names = screen_names or [f"Screen {i}" for i in range(num_screens)]
    corner_positions = ["TL", "TR", "BR", "BL"]
    
    all_tag_images = []
    
    for screen_idx in range(num_screens):
        screen_name = screen_names[screen_idx] if screen_idx < len(screen_names) else f"Screen {screen_idx}"
        base_id = screen_idx * 4
        
        print(f"\n{screen_name} (IDs {base_id}-{base_id + 3}):")
        
        screen_tags = []
        for corner_idx, corner in enumerate(corner_positions):
            tag_id = base_id + corner_idx
            label = f"ID {tag_id} - {screen_name} {corner}"
            filename = output_dir / f"screen{screen_idx}_tag{tag_id}_{corner.lower()}.png"
            generate_single_tag(tag_id, filename, size, label)
            print(f"  {filename.name}")
            screen_tags.append(cv2.imread(str(filename)))
        
        # Create per-screen printable sheet
        row1 = np.hstack([screen_tags[0], screen_tags[1]])
        row2 = np.hstack([screen_tags[3], screen_tags[2]])
        screen_sheet = np.vstack([row1, row2])
        
        sheet_path = output_dir / f"screen{screen_idx}_printable.png"
        cv2.imwrite(str(sheet_path), screen_sheet)
        print(f"  Printable: {sheet_path.name}")
        
        all_tag_images.append(screen_sheet)
    
    # Combined sheet with all screens
    if num_screens > 1:
        combined = np.vstack(all_tag_images)
        combined_path = output_dir / "all_screens_printable.png"
        cv2.imwrite(str(combined_path), combined)
        print(f"\nCombined all screens: {combined_path}")


def prompt_for_screens() -> tuple[int, list[str]]:
    """Interactively ask user for number of screens and their names."""
    print("=" * 50)
    print("AprilTag Generator (tag16h5)")
    print("=" * 50)
    print(f"\nEach screen requires 4 AprilTags (one per corner).")
    print(f"Maximum supported: {MAX_SCREENS} screens (30 tags / 4 per screen)\n")
    
    while True:
        try:
            num_screens = int(input("How many screens do you want to set up? "))
            if num_screens < 1:
                print("Please enter at least 1 screen.")
                continue
            if num_screens > MAX_SCREENS:
                print(f"Maximum {MAX_SCREENS} screens supported.")
                continue
            break
        except ValueError:
            print("Please enter a valid number.")
    
    print(f"\nYou can optionally name each screen (press Enter to skip):")
    names = []
    for i in range(num_screens):
        default_name = f"Screen {i}"
        name = input(f"  Screen {i} name [{default_name}]: ").strip()
        names.append(name if name else default_name)
    
    return num_screens, names


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate AprilTag markers (tag16h5 family)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode - prompts for number of screens
  python generate_tags.py
  
  # Generate tags for 2 screens
  python generate_tags.py --screens 2
  
  # Generate tags for 3 screens with names
  python generate_tags.py --screens 3 --names Left Center Right
  
  # Generate specific tag IDs
  python generate_tags.py --ids 0 4 8
  
  # Generate a range of tags
  python generate_tags.py --range 0 12
  
  # Custom output directory and size
  python generate_tags.py --screens 2 --output my_tags --size 400

Tag16h5: 30 tags (IDs 0-29), supports up to 7 screens
        """,
    )
    parser.add_argument(
        "--ids",
        type=int,
        nargs="+",
        help="Specific tag IDs to generate (0-29)",
    )
    parser.add_argument(
        "--range",
        type=int,
        nargs=2,
        metavar=("START", "END"),
        help="Generate tags in range [START, END)",
    )
    parser.add_argument(
        "--screens",
        type=int,
        metavar="N",
        help=f"Generate tags for N screens (4 tags each, max {MAX_SCREENS})",
    )
    parser.add_argument(
        "--names",
        nargs="+",
        help="Screen names (use with --screens)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path(__file__).parent / "tags",
        help="Output directory (default: ./tags)",
    )
    parser.add_argument(
        "--size", "-s",
        type=int,
        default=300,
        help="Tag size in pixels (default: 300)",
    )
    
    args = parser.parse_args()
    
    if args.screens:
        # Generate multi-screen tags (CLI mode)
        generate_multiscreen_tags(args.screens, args.output, args.size, args.names)
        print(f"\nDone! Each screen needs 4 tags at its corners.")
        print("Tag IDs per screen:")
        for i in range(args.screens):
            print(f"  Screen {i}: IDs {i*4}, {i*4+1}, {i*4+2}, {i*4+3}")
    elif args.ids:
        # Generate specific IDs
        generate_tags(args.ids, args.output, args.size)
    elif args.range:
        # Generate range of IDs
        start, end = args.range
        generate_tags(list(range(start, end)), args.output, args.size)
    else:
        # Interactive mode
        num_screens, names = prompt_for_screens()
        
        print(f"\nGenerating tags for {num_screens} screen(s)...\n")
        generate_multiscreen_tags(num_screens, args.output, args.size, names)
        
        print("\n" + "=" * 50)
        print("SETUP INSTRUCTIONS")
        print("=" * 50)
        print(f"\n1. Print the tag sheets from: {args.output}/")
        print("2. Cut out individual tags")
        print("3. Place 4 tags at each screen's corners:\n")
        
        for i in range(num_screens):
            base_id = i * 4
            print(f"   {names[i]}:")
            print(f"     Top-Left: ID {base_id}    Top-Right: ID {base_id + 1}")
            print(f"     Bottom-Left: ID {base_id + 3}    Bottom-Right: ID {base_id + 2}")
            print()


if __name__ == "__main__":
    main()
