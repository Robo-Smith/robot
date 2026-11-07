"""Draw the current inference result onto a copy of its matching camera frame."""


def annotate_frame(frame, boxes, scores, following=False, elapsed=0.0, error=''):
    import cv2
    image = frame.copy()
    target = max(range(len(boxes)), key=lambda i: boxes[i][2] * boxes[i][3], default=None)
    stale = elapsed > .5
    for index, ((x, y, w, h), score) in enumerate(zip(boxes, scores)):
        selected = following and index == target
        color = (0, 190, 255) if selected else (100, 235, 110)
        if stale:
            color = (100, 100, 240)
        label = ('Follow target' if selected else 'Person') + f' {float(score):.0%}'
        cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
        cv2.putText(image, label, (max(2, x), max(54, y - 7)),
                    cv2.FONT_HERSHEY_SIMPLEX, .5, color, 1, cv2.LINE_AA)
    if error:
        label, color = 'Detection unavailable', (100, 100, 255)
    elif stale:
        label, color = 'Detection stale - follow stopped' if following else 'Detection stale', (100, 100, 255)
    elif not boxes:
        label, color = 'No person detected', (0, 195, 255)
    else:
        label, color = f'{len(boxes)} person(s) detected', (100, 235, 110)
    label += ' | Follow mode' if following else ' | Preview only'
    cv2.rectangle(image, (0, 0), (image.shape[1], 34), (15, 23, 18), -1)
    cv2.putText(image, label, (10, 23), cv2.FONT_HERSHEY_SIMPLEX, .53, color, 1, cv2.LINE_AA)
    return image
