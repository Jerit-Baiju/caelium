import os
from datetime import datetime, timezone

# Define the destination directory
DESTINATION_DIR = "exports"


def any_in(checks, target):
    for check in checks:
        if check in target:
            return True
    return False


def check_type(raw_name, other=False):
    if raw_name.endswith(".opus"):
        return "Voice Notes"
    if "record" in raw_name.lower():
        return "Screen Records"
    if raw_name.startswith("Screenshot"):
        return "Screenshots"
    if raw_name.endswith((".mp4", ".MP4")):
        return "Videos"
    if any_in([")_", "call"], raw_name.lower()):
        return "Call Records"
    if raw_name.startswith("DOC") or raw_name.endswith((".pdf", ".csv")):
        return "Documents"
    return "Other" if other else "main"


def get_directory_path(filename):
    """
    Get the destination directory path for a file based on its timestamp.
    Returns a list of directory names that form the path hierarchy.

    Args:
        filename (str): The name of the file to process

    Returns:
        list: A list of directory names forming the hierarchy, or None if path cannot be determined
    """
    timestamp1 = ("IMG_", "VID_", "MVIMG_", "SAVE_", "MVIMG_")
    timestamp2 = ("IMG-", "AUD-", "PTT-", "VID-", "null-", "DOC")
    timestamp3 = ("2017-", "2018-", "2019-", "2020-", "2021-", "2022-", "2023-", "2024-")
    timestamp4 = ("2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024")
    timestamp5 = ("Screenshot_",)
    timestamp6 = ("Screenrecorder-",)
    timestamp7 = ("IMG20",)
    timestamp8 = (")_", "call_")
    timestamp9 = ("WhatsApp ", "Screen Recording")
    timestamp10 = ("Screenshot ",)
    timestamp11 = ("VID",)

    # Skip hidden files
    if filename.startswith("."):
        return None

    # Skip text files (chat files) as requested
    if filename.endswith(".txt"):
        return None

    try:
        is_other = False
        try:
            is_raw = bool(datetime.fromtimestamp(float(filename.split(".")[0]), timezone.utc))
        except:
            is_raw = False

        if (
            not filename.startswith(
                timestamp1
                + timestamp2
                + timestamp3
                + timestamp4
                + timestamp5
                + timestamp6
                + timestamp7
                + timestamp9
                + timestamp10
                + timestamp11
            )
            and not any_in(timestamp8, filename)
        ) and not is_raw:
            is_other = True
            timestamp = str(datetime.today().strftime(r"%Y%m%d"))
        elif filename.startswith(timestamp1):
            timestamp = filename.split("_")[1]
        elif filename.startswith(timestamp2):
            timestamp = filename.split("-")[1]
        elif filename.startswith(timestamp3):
            pre = str(filename.split(".")[0]).split("-")
            timestamp = f"{pre[0]}{pre[1]}{pre[2]}"
        elif filename.startswith(timestamp4):
            timestamp = filename.split("_")[0]
        elif filename.startswith(timestamp5):
            if "com." in filename:
                pre = str(filename.split("_")[1]).split("-")
                timestamp = f"{pre[0]}{pre[1]}{pre[2]}"
            else:
                timestamp = str(filename.split("_")[1]).split("-", maxsplit=1)[0]
        elif filename.startswith(timestamp6):
            pre = filename.split("-")
            timestamp = f"{pre[1]}{pre[2]}{pre[3]}"
        elif filename.startswith(timestamp7):
            timestamp = filename.split(".")[0][3:11]
        elif any_in(timestamp8, filename):
            timestamp = f"{filename.split('_')[1].split('.')[0]}"[:8]
        elif filename.startswith(timestamp9):
            timestamp = f"{filename.split(' ')[2].replace('-', '')}"
        elif filename.startswith(timestamp10):
            timestamp = f"{filename.split(' ')[1].replace('-', '')}"
        elif filename.startswith(timestamp11):
            timestamp = f"{filename[3:11]}"
        elif is_raw:
            timestamp = datetime.fromtimestamp(float(filename.split(".")[0]), timezone.utc).strftime("%Y%m%d")
        else:
            return None

        try:
            date = datetime.strptime(timestamp, "%Y%m%d")
        except:
            timestamp = str(datetime.today().strftime(r"%Y%m%d"))
            date = datetime.strptime(timestamp, "%Y%m%d")
        print(date)
        # Create directory path hierarchy as a list
        path_hierarchy = [str(date.year), date.strftime("%B")]

        # Add file type folder if needed
        file_type = check_type(filename, is_other)
        if file_type != "main":
            path_hierarchy.append(file_type)

        return path_hierarchy

    except:
        return None


def get_file_destination(filename, destination_dir=DESTINATION_DIR):
    """
    Get the destination filepath for a file based on its timestamp.

    Args:
        filename (str): The name of the file to process
        destination_dir (str): The base destination directory

    Returns:
        str: The destination filepath, or None if the filepath cannot be determined
    """
    path_hierarchy = get_directory_path(filename)
    if not path_hierarchy:
        return None

    # Build the full path
    current_path = destination_dir
    for folder in path_hierarchy:
        current_path = os.path.join(current_path, folder)

    return os.path.join(current_path, filename)


def extract_date_from_filename(filename):
    """
    Extract the date from a filename using the same logic as get_directory_path.

    Args:
        filename (str): The name of the file to process

    Returns:
        datetime: The extracted date, or today's date if extraction fails
    """
    timestamp1 = ("IMG_", "VID_", "MVIMG_", "SAVE_", "MVIMG_")
    timestamp2 = ("IMG-", "AUD-", "PTT-", "VID-", "null-", "DOC")
    timestamp3 = ("2017-", "2018-", "2019-", "2020-", "2021-", "2022-", "2023-", "2024-")
    timestamp4 = ("2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024")
    timestamp5 = ("Screenshot_",)
    timestamp6 = ("Screenrecorder-",)
    timestamp7 = ("IMG20",)
    timestamp8 = (")_", "call_")
    timestamp9 = ("WhatsApp ", "Screen Recording")
    timestamp10 = ("Screenshot ",)
    timestamp11 = ("VID",)

    try:
        try:
            is_raw = bool(datetime.fromtimestamp(float(filename.split(".")[0]), timezone.utc))
        except:
            is_raw = False

        if (
            not filename.startswith(
                timestamp1
                + timestamp2
                + timestamp3
                + timestamp4
                + timestamp5
                + timestamp6
                + timestamp7
                + timestamp9
                + timestamp10
                + timestamp11
            )
            and not any_in(timestamp8, filename)
        ) and not is_raw:
            timestamp = str(datetime.today().strftime(r"%Y%m%d"))
        elif filename.startswith(timestamp1):
            timestamp = filename.split("_")[1]
        elif filename.startswith(timestamp2):
            timestamp = filename.split("-")[1]
        elif filename.startswith(timestamp3):
            pre = str(filename.split(".")[0]).split("-")
            timestamp = f"{pre[0]}{pre[1]}{pre[2]}"
        elif filename.startswith(timestamp4):
            timestamp = filename.split("_")[0]
        elif filename.startswith(timestamp5):
            if "com." in filename:
                pre = str(filename.split("_")[1]).split("-")
                timestamp = f"{pre[0]}{pre[1]}{pre[2]}"
            else:
                timestamp = str(filename.split("_")[1]).split("-", maxsplit=1)[0]
        elif filename.startswith(timestamp6):
            pre = filename.split("-")
            timestamp = f"{pre[1]}{pre[2]}{pre[3]}"
        elif filename.startswith(timestamp7):
            timestamp = filename.split(".")[0][3:11]
        elif any_in(timestamp8, filename):
            timestamp = f"{filename.split('_')[1].split('.')[0]}"[:8]
        elif filename.startswith(timestamp9):
            timestamp = f"{filename.split(' ')[2].replace('-', '')}"
        elif filename.startswith(timestamp10):
            timestamp = f"{filename.split(' ')[1].replace('-', '')}"
        elif filename.startswith(timestamp11):
            timestamp = f"{filename[3:11]}"
        elif is_raw:
            timestamp = datetime.fromtimestamp(float(filename.split(".")[0]), timezone.utc).strftime("%Y%m%d")
        else:
            return datetime.today()

        try:
            date = datetime.strptime(timestamp, "%Y%m%d")
            return date
        except:
            return datetime.today()

    except:
        return datetime.today()
