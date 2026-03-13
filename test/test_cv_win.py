import cv2
import time

cv2.namedWindow('Test', cv2.WINDOW_NORMAL)
cv2.setWindowProperty('Test', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

img = cv2.imread('picture/edit/Nestle-full-edit02.pgm')
cv2.imshow('Test', img)

prop = cv2.getWindowProperty('Test', cv2.WND_PROP_VISIBLE)
print(f"Property visible: {prop}")
cv2.waitKey(100)
prop = cv2.getWindowProperty('Test', cv2.WND_PROP_VISIBLE)
print(f"Property visible after waitKey: {prop}")
cv2.destroyAllWindows()
