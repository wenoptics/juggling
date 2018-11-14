import cv2, math, numpy as np

# --------------------- START PARAMETERS -----------------------
# h,s,v range of the object to be tracked
#color_values = 100,60,50,170,255,185 #pink
#color_values = 19,37,151,50,206,255 # yellow
#color_values = 105,130,0,130,228,128 #blue
#color_values = 50,38,101,83,204,255 #green
color_values = 120,110,0,193,255,255 #purple 

# What is the maximum distance a ball can move between two frames?
# For 1080p 120fps video: 20 is a good value
max_distance = 20

# How big is a ball? This is the dark blue circle
ball_size = 9
# contour_ball_size = ball size in pixels / 5
# 20 is a good value
contour_ball_size = 20

# The tracker 'snaps' onto the ball's position.
# This is the big light blue circle
global max_snap_distance
# max_snap_distance = 1.5 * ball_size
max_snap_distance = 15

# Pick a path to save the data
output_path = '/home/stephen/Desktop/data/1.csv'

# Capture your source video
cap = cv2.VideoCapture('/home/stephen/Desktop/source_vids/ss9131_id_161.MP4')
# -------------------- END PARAMETERS -----------------------

# If the tracker gets lost, the last few tracking values are erroneous
# Preserving the history allows the user can skip back a bit when a tracker error occurs
p_imgs, history_length, history_idx = [], 80, 0

# Parameters for the text in the user instructions
font, scale, color, thick = cv2.FONT_HERSHEY_SIMPLEX, .5, (255,0,0), 1

# Takes an image, and a lower and upper bound
# Returns only the parts of the image in bounds
def only_color(frame, color_valeus, p_position):
    # Create a mask
    mask = np.zeros((frame.shape[0], frame.shape[1]), np.uint8)
    # Draw a circle around the last known position of the ball
    # Everything outside the circle is value=0
    # Only objects inside the circle are possible juggling balls
    mask = cv2.circle(mask, p_position, max_snap_distance, 255, -1)
    # Mask out the image
    frame = cv2.bitwise_and(frame, frame, mask=mask)    
    # Convert BGR to HSV
    b,r,g,b1,r1,g1 = color_values
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # Define range of blue color in HSV
    lower = np.array([b,r,g])
    upper = np.array([b1,r1,g1])
    # Threshold the HSV image to get only blue colors
    mask = cv2.inRange(hsv, lower, upper)
    # Bitwise-AND mask and original image
    res = cv2.bitwise_and(frame,frame, mask= mask)
    return res, mask

# Finds the largest contour in a list of contours
# Returns a single contour
def largest_contour(contours):
    c = max(contours, key=cv2.contourArea)
    return c[0]

# Takes an image and the threshold value returns the contours
def get_contours(im):
    imgray = cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    _ ,thresh = cv2.threshold(imgray,0,255,0)
    _, contours, _ = cv2.findContours(thresh,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    return contours

# Finds the center of a contour
# Takes a single contour
# Returns (x,y) position of the contour
def contour_center(c):
    M = cv2.moments(c)
    try: center = int(M['m10']/M['m00']), int(M['m01']/M['m00'])
    except: center = 0,0
    return center

# Finds the most likely position of the ball in an image using color
# Returns xy coordinates
def find_ball_by_color(img, color_values, ball_position):
    # Filter the image for the specific ball color
    img, mask = only_color(img, color_values, ball_position)    
    # Find the contours in the image
    contours = get_contours(img)
    # Start with values that are definitely out of the snap range
    nearest_ball = 100000000
    nearest_snap_possibility = (10000,10000)
    # Iterate through the contours
    for contour in contours:
        # Check if a contour is big enough to be considered a ball
        if cv2.contourArea(contour)>contour_ball_size:
            # Get the center of the contour
            center = contour_center(contour)
            # This contour is the nearest one to the ball, it is the most likely snap position
            if distance(center, ball_position) < nearest_ball:
                # Save this as the nearest likely ball
                nearest_snap_possibility = center
    # Return the mostly likely location of the ball in the image
    return nearest_snap_possibility

def distance(a,b): return math.sqrt((a[0]-b[0])**2+(a[1]-b[1])**2)

# Check for maximum distance failure, returns boolean
def max_distance_failure(a,b):
    is_failure = False
    if distance(a,b)> max_distance:
        is_failure = True
        print("Max distance failure: ", distance(a,b))
    return is_failure

# Parameters of lk optical flow
lk_params = dict(winSize = (ball_size, ball_size),
                 maxLevel = 5,
                 criteria = (cv2.TERM_CRITERIA_EPS |
                             cv2.TERM_CRITERIA_COUNT, 5, 0.03))

# Mouse callback function
global click_list
positions, click_list = [], []
def callback(event, x, y, flags, param):
    if event == 1: click_list.append((x,y))
cv2.namedWindow('img')
cv2.setMouseCallback('img', callback)

# Initialize frame_number
frame_number = 0
wait_time = 0

# Initialize tracker value, this will get reset by the user
p0 = np.array([[[0,0]]], np.float32)

# Main loop
while True:
    # Read frame of video (either from the source or the history)
    if history_idx == 0:
        ret, img = cap.read()
        # Save the frame to the history
        if ret: p_imgs.append(img.copy())
    else:
        # Read a frame from the history
        img = p_imgs.pop(0)
        history_idx -= 1

    # Break if the video is over
    try:h,w,e = img.shape
    except: break

    # Optical flow works in single channel, so save the previous gray image
    try: old_gray = img_gray.copy()
    except: old_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    try: img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    except: break

    # Draw the previous ball positions on the screen
    idx = 0
    while idx < 40 and idx < len(positions)-3:
        a = positions[-(idx+2)]
        b = positions[-(idx+1)]
        cv2.line(img, a,b, (255,255,255), 1)
        idx += 1

    # Track using optical flow
    # p1 is the value produced by the optical flow tracker
    p1, _, _ = cv2.calcOpticalFlowPyrLK(old_gray, img_gray,p0, None, **lk_params)

    # Convert the coordinates to integers for drawing
    xy  = int(p1[0][0][0]), int(p1[0][0][1])

    # Get the nearest likely snap position
    snap_position = find_ball_by_color(img, color_values, xy)
    # Draw a circle around the snap position
    cv2.circle(img, snap_position, max_snap_distance, (255,255,0), 1)
    # Is the likely position found using color close to the optical flow tracker
    if distance(snap_position, xy) < max_snap_distance:
        # The color value is a good one, so snap to that
        xy = snap_position
        p1 = np.array([[[snap_position[0], snap_position[1]]]], np.float32)

    # Check for a max distance failure
    if max_distance_failure(p0[0][0], p1[0][0]):
        wait_time = 0 # Stop the tracker
        p1 = p0 # Get rid of the erronious tracker value
        xy  = int(p1[0][0][0]), int(p1[0][0][1])
        cv2.putText(img, "Max Distance Tracker Failure", (50,25), font, scale, (0,0,255), thick, cv2.LINE_AA)
    else: p0 = p1 # Update p0 to p1
    
    # Make circle around ball to show the tracking point
    cv2.circle(img, xy, ball_size, (255,2,1), 1)

    # Write instructions to user
    if wait_time == 0:
        cv2.putText(img, "Click on ball and press F5 to reset tracker", (50,50), font, scale, color, thick, cv2.LINE_AA)
        if len(positions)>0:
            cv2.putText(img, "...or press F6 to continue to the next frame", (50,80), font, scale, color, thick, cv2.LINE_AA)
            cv2.putText(img, "...or press F7 to autotrack slowly", (50,110), font, scale, color, thick, cv2.LINE_AA)
            cv2.putText(img, "...or press F8 to autotrack at max speed", (50,140), font, scale, color, thick, cv2.LINE_AA)
    if wait_time == 1 or wait_time == 25:
        cv2.putText(img, "Auto-Tracking", (50,50), font, scale, color, thick, cv2.LINE_AA)
        cv2.putText(img, "Press any key on mistake", (50,80), font, scale, color, thick, cv2.LINE_AA)
        cv2.putText(img, "Press F6 to pause", (50,110), font, scale, color, thick, cv2.LINE_AA)
    

    # Show frame and wait
    cv2.imshow('img', img)
    k = cv2.waitKey(wait_time)
    if k ==27: break
    
    # User Presses F6, advance to the next frame and wait
    if k == 195: wait_time = 0
    # User presses F7, play slowly
    if k == 196: wait_time = 25
    # User presses F8, max computer resources
    if k == 197: wait_time = 1
    # User wants to reset the tracker to the last click position 
    if k == 194: #F5
        # Get the user's input
        xy = click_list[-1]
        # Set the tracker to this user input
        p0 = np.array([[xy]], np.float32)
        # Advance to the next frame, but pause
        wait_time = 0    

    # Add tracked location to data
    positions.append(xy)

    # If there are enough items in the history, remove the oldest one
    if len(p_imgs)>history_length: p_imgs.pop(0)

    # User has paused any other key because the tracker has gotten lost
    if k < 194 and k >10:
        # Pause
        wait_time = 0
        # Get the history length
        history_idx = history_length
        # Remove the last few positions, that are errors from a broken tracker
        positions = positions[:-history_length]

# Close the window and release the source video
cv2.destroyAllWindows()
cap.release()

# Write data to a csv (spreadsheet) file
import csv
with open(output_path, 'w') as csvfile:
    fieldnames = ['x_position', 'y_position']
    writer = csv.DictWriter(csvfile, fieldnames = fieldnames)
    writer.writeheader()
    for position in positions:
        x, y = position[0], position[1]
        writer.writerow({'x_position': x, 'y_position': y})
print( 'finished writing data')