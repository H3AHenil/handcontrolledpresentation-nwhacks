def finger_to_coordinate(box: tuple[int, int, int, int], finger_coord: tuple[int, int]):
    """
    box: (x1, y1, x2, y2)
    finger_coord: (finger_x, finger_y)

    Returns:
        (rel_x, rel_y) in [0,1] or (-1,-1) if outside
    """
    x1, y1, x2, y2 = box
    fx, fy = finger_coord
    if x1 <= fx <= x2 and y1 <= fy <= y2:
        rel_x = (fx - x1) / (x2 - x1)
        rel_y = (fy - y1) / (y2 - y1)
        return rel_x, rel_y
    else:
        return -1, -1
    

