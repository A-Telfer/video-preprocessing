#!/usr/bin/env python
# coding: utf-8

# # Transcoding a Large Experiment
# Contact: andretelfer@cmail.carleton.ca
# 
# ## Introduction
# ### What is transcoding and why do we do it?
# Transcoding is the process of converting video from one format to another. 
# 
# In behavior, this is useful because videos directly from cameras are often overly large. By transcoding we can reduce the size of videos by half or more. Additionally, we can also resize videos (e.g. from 4K resolution to 720p), remove sound, and perform other useful functions. 
# 
# In some cases, I have shrunk experiments of over 100GB to <2GB with no difference to scoring. This makes using automated tools, such as deeplabcut, a lot faster. Furthermore it's a lot easier to transfer the files around to students or publish them online. 
# 
# ### What's covered here
# Here we explore a large experiment with an inconsistent structure and lots of irrelevant data
# 
# We're going to focus on a few main tasks
# 1. Exploring the file systems: Finding all of the relevant videos
# 2. Video details: Getting high level details from them to later verify everything was copied correctly (such as time). We also want to see if the videos themselves are very different and need lots of preprocessing.
# 3. Transcoding the videos into a new folder using `ffmpeg`
# 
# ```{note}
# In this case, we do not resize the videos because they are fairly low quality. However you can easily add option to the ffmpeg command in the transcoding step to this.
# ```
# 
# ### What's not covered here
# This notebook is aimed at researchers who already have some knowledge but may want to expand/improve their methods using the tips here
# 
# - Python knowledge and some basics including some basic bash is assumed
# - knowledge of ffmpeg is helpful
# - With some basics, missing knowledge is mostly searchable. 
# 
# For questions or suggestions, reach out to me at andretelfer@cmail.carleton.ca

# ## 1. Exploring the file system

# Lets first find which drives are mounted

# In[52]:


ls /media/andre


# I know that the first 3 drives contain experimental data, the last `maternal` drive is where I plan to store the transcoded videos

# In[53]:


from pathlib import Path 

# On my system, this is where the storage devices are mounted
MOUNT_POINT = Path("/media/andre")

# The names of drives the data exists
DRIVES = [
    '11D9-5C57',
    '5161-4A93',
    '9B57-8640'
]

# Where we want to store the videos
OUTPUT_DRIVE = MOUNT_POINT / 'maternal'


# ### Size of Original Datasets

# Lets see how big our original dataset is

# In[54]:


get_ipython().run_cell_magic('time', '', '\ntotal_size = 0\nfor drive in DRIVES:\n    # glob is a useful tool for searching folders, here we tell it to find every file\n    files = (MOUNT_POINT / drive).glob(\'**/*\')\n    \n    # Only keep the files (discard directories)\n    files = list(filter(lambda x: x.is_file(), files)) \n    \n    # Get the size of each file\n    sizes = list(map(lambda x: x.stat().st_size, files)) \n    size = sum(sizes)\n    total_size += size\n    \n    # print the size in gigabytes\n    print(f"Drive {drive} is {size / 1e9:.2f}GB")\n    \n# print the total size\nprint(f"Total: {total_size / 1e9:.2f}GB")')


# ### What types of videos are in the dataset

# Eek, over 2TB of data. But do we really need all of these files? I only want the videos to transcode, and can ignore everything else
# 
# Since videos can have many file extensions, lets print out all of the file extensions so we can identify the video ones.

# In[55]:


total_size = 0

# Use a set instead of a list to ignore duplicates
extensions = set()
for drive in DRIVES:
    files = (MOUNT_POINT / drive).glob('**/*')
    files = list(filter(lambda x: x.is_file(), files))
    
    # Get the extensions
    for filepath in files:
        fileparts = filepath.parts[-1].split('.')
        
        # Some files don't have extensions, ignore those
        if len(fileparts) > 1:
            extensions.add(fileparts[-1])

print("Extensions: ", list(extensions))


# ### Further narrowing down the videos
# 
# Looking through all of the extensions I can see only 2 video related extensions: mp4 and MPG - every other file we can ignore for now
# 
# However we may not want all of the videos, sometimes experimenters will horde discarded videos in folders like "temp". Let's make sure we only get videos that appear meaningful. 
# 
# ... but first lets check how many videos

# In[56]:


for drive in DRIVES:
    videos = (
        list((MOUNT_POINT / drive).glob('**/*.mp4')) + 
        list((MOUNT_POINT / drive).glob('**/*.MPG'))
    )
    
    print(f"Number of videos in {drive}: {len(videos)}")


# Again, eek. But I can't think of a way around seeing them all so lets print them out anyways.

# In[57]:


for drive in DRIVES:
    videos = (
        list((MOUNT_POINT / drive).glob('**/*.mp4')) + 
        list((MOUNT_POINT / drive).glob('**/*.MPG'))
    )
    videos = list(map(str, videos)) # makes things a bit prettier
    print(videos)


# After lots of reading, I can say fairly confidently there are two types of videos we want to ignore
# 1. Ones that begin with a `.` or are in folders that begin with a `.`. These videos are hidden and are probably artifacts from the camera or some other software.
# 2. Videos in folders that begin with $RECYCLE, 
# 
# For now let's say the rest of the videos are useful, we can sort them out later by viewing them. There are too many to look through each one right now.

# In[58]:


def is_visible(filepath):
    for part in filepath.parts:
        if part.startswith('.'):
            return False
        
    return True

def is_not_recycled(filepath):
    for part in filepath.parts:
        if part.startswith('$RECYCLE'):
            return False
        
    return True
    
for drive in DRIVES:
    videos = (
        list((MOUNT_POINT / drive).glob('**/*.mp4')) + 
        list((MOUNT_POINT / drive).glob('**/*.MPG'))
    )
    
    all_videos_len = len(videos)
    videos = list(filter(is_visible, videos))
    videos = list(filter(is_not_recycled, videos))
    after_filtering_len = len(videos)
    
    print(f"Length of videos before filtering: {all_videos_len:4}, after: {after_filtering_len}")


# ### Visualizing structure of folders
# Sometimes the folders are very disorganized and its hard to get a big picture of what data we have by looking into each folder one at a time

# In[92]:


pip install -q treelib


# In[91]:


import treelib

tree = treelib.Tree()
tree.create_node('/', '/')
for video in tqdm(all_videos):
    video = video.relative_to(MOUNT_POINT)
    parts = video.parts[:-1] # don't include filename
    for i in range(1,len(parts)+1):
        uid = '/'.join(parts[:i])
        name = parts[i-1]
        
        if tree.contains(uid):
            continue 
        
        # include parent
        if i > 1:
            parent_uid = '/'.join(parts[:i-1])
            tree.create_node(name, uid, parent=parent_uid)
        else:
            tree.create_node(name, uid, parent='/')
            
tree.show()


# We can save the whole output to a file to view it there

# ## 2. Video Details

# ### Getting Video Metadata
# 
# So we know how many videos are in each folder, and how big the files are. But how long are the videos? Are they all the same size? (this can be very important because many algorithms struggle with inconsistent scales)
# 
# Knowing this metadata is also important because it can help us validate the transcoded videos later.

# In[59]:


all_videos = []
for drive in DRIVES:
    # Get all mp4/MPG video files
    videos = (
        list((MOUNT_POINT / drive).glob('**/*.mp4')) + 
        list((MOUNT_POINT / drive).glob('**/*.MPG'))
    )
    
    # Filter out the hidden and recycled videos
    videos = list(filter(is_visible, videos))
    videos = list(filter(is_not_recycled, videos))
    all_videos += videos


# In[60]:


import pandas as pd
import cv2
from tqdm import tqdm

metadata = []
for video in tqdm(all_videos):
    cap = cv2.VideoCapture(str(video))
    _metadata = {
        'file': video,
        'filetype': video.parts[-1].split('.')[-1],
        'frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        'fps': float(cap.get(cv2.CAP_PROP_FPS)),
        'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    }
    metadata.append(_metadata)
    
metadata_df = pd.DataFrame(metadata)
metadata_df


# ### Total duration

# In[61]:


(metadata_df.frames / metadata_df.fps).sum()


# ... That doesn't look right. What's going on?

# In[62]:


metadata_df.describe()


# Apparently the minimum number of frames for a video is `-3.074457e+15`... clearly there was a problem there. 
# 
# Let's see what videos are causing the problem

# In[63]:


metadata_df.loc[metadata_df.frames < 0]


# Bad videos. Fortunately there's only a few so we can ignore them and deal with them manually later. Hopefully transcoding them will correct it.

# In[64]:


outlier_rows = metadata_df.frames < 0
metadata_df.loc[outlier_rows, 'frames'] = None
metadata_df.loc[outlier_rows]


# Great! we can get the total duration

# In[65]:


(metadata_df.frames / metadata_df.fps).sum()


# In human language...

# In[66]:


total_seconds = (metadata_df.frames / metadata_df.fps).sum()
total_days = total_seconds / 60 / 60 / 24 # 60s->1m, 60m->1h, 24h->1d
print(f"Total days of videos: {total_days:.1f}")


# Lets consider ourselves fortunate we're not going to score this manually. Scoring just a few hours of videos is a slow process already, scoring 151 days of video would probably take an entire PhD

# ### Any other differences in size, etc?

# In[67]:


metadata_df.describe()


# All of the videos have exactly the same height, and pretty much the same fps. There are videos with different widths however. Lets see all of the widths.

# In[68]:


metadata_df.width.unique()


# Only two video widths, 704px and 720px. Lets see if these are from the two different filetypes `mp4` and `MPG`

# In[69]:


metadata_df.loc[metadata_df.width==704].describe()


# In[70]:


metadata_df.loc[metadata_df.width==704].sample(3)


# In[71]:


metadata_df.loc[metadata_df.width==720].describe()


# In[72]:


metadata_df.loc[metadata_df.width==720].sample(3)


# Yep! At a glance it looks like the mp4 files have a width of 704 and all of the MPG files have a width of 720.
# 
# I'm pretty satisfied with understanding the videos at this point. The differences in videos appear minor, likely due to a camera change. We also know that when we finish transcoding we expect our new videos to have a total duration of about 13082190 seconds.
# 
# We also identified a few videos that may be damaged which we can manually check over later.

# ## 3. Transcoding the videos

# In[73]:


print(f"We're not going to reorganize our {len(all_videos)} videos here.")


# Instead we'll just transcode them over in their original structure for now. The transcoded videos will still be smaller, and we can safely manually reorganize them without risking losing anything since we still have the originals.

# ### Creating a bash file for long runs

# The following script generates a bash file that can be run to transcode all of the files
# 
# The tool we use to actually do the transcoding is called ffmpeg. It's very versatile, and has way too many options to learn all of them, so you can search up what you need when you need them.
# 
# ffmpeg commands don't have to be complicated, a simple one would be 
# ```bash
# ffmpeg -i <your-input-file> <your-output-file>
# ```
# 
# We can do things like resizing the video or changing quality, in the below command I decrease the video quality slightly using `-crf 24`. This should shrinkg their size a lot.

# In[74]:


with open('transcode.sh', 'w') as fp:
    lines = []
    for video in all_videos:
        relative_path = video.relative_to(MOUNT_POINT)
        output_filepath = OUTPUT_DRIVE / relative_path
    
        cmd = (
            "mkdir -p {} &&" # make a new directory if necessary
            "ffmpeg -y -hwaccel cuda -hwaccel_output_format cuda -extra_hw_frames 4 -i '{}' " # the input file and flags
            "-c:v h264_nvenc -crf 24 '{}'\n" # the output file and flags
        ).format(output_filepath.parent, video, output_filepath)
        
        lines.append(cmd)
        
    fp.writelines(lines)


# This is what the bash file looks like (but a lot more lines)

# In[75]:


get_ipython().system(' head -n 3 transcode.sh')


# I've now started running this bash script. I'll see you in a few days!

# ### Veriftying videos
# ... Well, I'm a bit impatient, so I'm not going to wait a few days. Let's check to see how things are going after an hour.
# 
# Note we expect one video to not match/be readable as the bash script is still running and transcoding away as I write this.

# In[76]:


transcoded_videos = (
    list(OUTPUT_DRIVE.glob('**/*.mp4')) + 
    list(OUTPUT_DRIVE.glob('**/*.MPG'))
)

metadata = []
for transcoded_video in tqdm(transcoded_videos):
    relative_path = transcoded_video.relative_to(OUTPUT_DRIVE)
    original_video = MOUNT_POINT / relative_path
    
    original_cap = cv2.VideoCapture(str(original_video))
    transcoded_cap = cv2.VideoCapture(str(transcoded_video))
    
    _metadata = {
        'file': original_video,
        'transcoded_file': transcoded_video,
        'frames': int(original_cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        'transcoded_frames': int(transcoded_cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        'filesize_mb': round(original_video.stat().st_size / 1e6, 1), 
        'transcoded_filesize_mb': round(transcoded_video.stat().st_size / 1e6, 1), 
    }
    metadata.append(_metadata)
    
transcoded_metadata_df = pd.DataFrame(metadata)
transcoded_metadata_df


# #### Quality checks

# ##### Extracting individual frames

# In[ ]:





# #### Stacking videos
# 
# ```
# ffmpeg -i original.mp4 -i transcoded.mp4 -filter_complex vstack=inputs=2 stacked-view.mp4
# ```
