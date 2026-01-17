"""
Generate printable AprilTag images.

Supports the full tag36h11 family (587 tags, IDs 0-586).

Default corner tags:
- ID 0: Top-left corner
- ID 1: Top-right corner
- ID 2: Bottom-right corner
- ID 3: Bottom-left corner
"""

from pathlib import Path

import cv2
import numpy as np

# AprilTag dictionary for tag36h11
APRILTAG_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)


def generate_apriltag_36h11(tag_id: int, size: int = 200) -> np.ndarray:
    """
    Generate a tag36h11 AprilTag image.
    
    Args:
        tag_id: Tag ID (0-586 for tag36h11)
        size: Output image size in pixels
        
    Returns:
        Grayscale image of the tag
    """
    if not 0 <= tag_id <= 586:
        raise ValueError(f"Tag ID must be 0-586 for tag36h11, got {tag_id}")
    
    # Generate using OpenCV's aruco module
    tag_img = cv2.aruco.generateImageMarker(APRILTAG_DICT, tag_id, size)
    return tag_img


def generate_single_tag(
    tag_id: int,
    output_path: Path,
    size: int = 300,
    label: str | None = None,
) -> Path:
    """
    Generate a single AprilTag and save to file.
    
    Args:
        tag_id: Tag ID (0-586)
        output_path: Where to save the PNG
        size: Tag size in pixels (before margin)
        label: Optional label text below the tag
        
    Returns:
        Path to the saved file
    """
    img = generate_apriltag_36h11(tag_id, size)
    
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
        tag_ids: List of tag IDs to generate
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
        num_screens: Number of screens/monitors
        output_dir: Directory to save tags
        size: Tag size in pixels
        screen_names: Optional names for screens (e.g., ["Left", "Right"])
    """
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


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate AprilTag markers (tag36h11 family)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate default corner tags (IDs 0-3) for single screen
  python generate_tags.py
  
  # Generate tags for 2 screens (IDs 0-7)
  python generate_tags.py --screens 2
  
  # Generate tags for 3 screens with names
  python generate_tags.py --screens 3 --names Left Center Right
  
  # Generate specific tag IDs
  python generate_tags.py --ids 10 20 30
  
  # Generate a range of tags
  python generate_tags.py --range 0 10
  
  # Custom output directory and size
  python generate_tags.py --ids 5 6 7 --output my_tags --size 400
        """,
    )
    parser.add_argument(
        "--ids",
        type=int,
        nargs="+",
        help="Specific tag IDs to generate (0-586)",
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
        help="Generate tags for N screens (4 tags each)",
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
        # Generate multi-screen tags
        generate_multiscreen_tags(
            args.screens,
            args.output,
            args.size,
            args.names,
        )
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
        # Default: generate corner tags for single screen
        generate_corner_tags(args.output, args.size)
        print("\nDone! Print 'all_tags_printable.png' and cut out the individual tags.")
        print("Place them at the corresponding corners of your monitor.")


if __name__ == "__main__":
    main()
