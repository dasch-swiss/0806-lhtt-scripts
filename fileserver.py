"""
    @author:        Stephan M. Unter
    @date:          25/02/2019 (BE)

    @description:   Fileserver class which upon creation either loads existing files (if possible) or
                    automatically registers all files on the fileserver.
"""

import os, json, re, time
import ext.scandir as scandir
from pprint import pprint


class Fileserver:
    def __init__(self, input_path_to_fileserver="", input_path_to_storage="", loading_existant=True):
        print("Creating a new Fileserver object.")

        if input_path_to_fileserver == "":
            self.path_fileserver = r"L:/Fileserver/"
        else:
            self.path_fileserver = r"" + input_path_to_fileserver

        if input_path_to_storage == "":
            self.path_storage = r"./storage/"
        else:
            self.path_storage = r"" + input_path_to_storage

        self.json_fileserver = "fileserver_json"
        self.path_skipped_folders = self.slash("./storage/skipped_folders.txt")
        self.path_skipped_extensions = self.slash("./storage/skipped_extensions.txt")
        self.skipped_folders = None
        self.skipped_extensions = None

        self.fileserver = {}
        if loading_existant:
            print("Loading existent Fileserver save.")
            self.load_json(self.path_storage + self.json_fileserver + ".txt")
        else:
            self.register_files()
            self.save_json()

        print("Initialization of Fileserver finished!")

    """
        @description:   This function simply prints all the available operations which can be
                        performed on the Fileserver()-object.
    """
    def help(self):
        print("help()")
        print("")
        print("add_folder_to_package(path_to_folder, package_name, recursive)")
        print("get_all_extensions()")
        print("get_files_by_extension(extension, print_skipped=False)")
        print("get_files_by_package(package_name, print_skipped=False)")
        print("get_files_without_db_connection(print_skipped=False)")
        print("get_list_of_packages()")
        print("get_unassigned_files(print_skipped=False)")
        print("get_unassigned_folders(print_skipped=False)")
        print("load_json(alternative_path='')")
        print("register_files()")
        print("save_json(alternative_path='')")
        print("update_entries(doublecheck=False)")
        return 0

    """
        @description:   This method registers all files on the Fileserver and stores the information
                        accordingly in a JSON storage. The JSON is structured by file paths. Each
                        subsequent JSON has currently the following keys:
                        
                        * extension [string] - file extension
                        * skip [bool] - if True, file should not be uploaded
                        * still_there [bool] - if True, the file is still assumed to be in place
                        * processed [bool] - if True, the data has already been uploaded
                        * name [string] - file name
                        * path [string] - file path /wo file name
                        * db_entries - another dictionary which contains information about the
                            relation between the file and database objects
                        * packages [Set] - set of packages this file has been assigned to
                            
        @return:        Nothing. The resulting dictionary is directly saved into self.fileserver.
    """
    def register_files(self, only_new=False):
        print("=> register_files()")

        file_counter = 0
        file_dict = {}

        for path, subdirs, files in scandir.walk(self.path_fileserver):
            for file in files:
                file_counter += 1
                file_path = self.slash(os.path.join(path, file))

                if only_new and file_path in self.fileserver:
                    continue

                file_ext = file[file.rfind(".") + 1:].lower()
                file_path_only = self.slash(path)
                still_there = True
                processed = False
                skip = False

                file_dict[file_path] = {
                    'extension' : file_ext,
                    'still_there' : still_there,
                    'processed' : processed,
                    'skip' : skip,
                    'path' : file_path_only,
                    'name' : file
                }

                if file_counter % 10000 == 0:
                    print("Files processed: {}".format(file_counter), flush=True)

        print("\nAll {} Files processed!\n".format(file_counter))
        self.fileserver = file_dict

    """
        @description:   This method flags all data entries which have been classified as unnecessary for
                        the upload as "skipped". Unnecessary are all files which either have an extension
                        which is not destined for upload, or files which are in folders which shall not or
                        cannot be taken into account.
                        
                        In the same way, this method checks whether files that have been registered in the
                        past are still in their place. If not, the "still_there" flag is set to False.
                        
        @parameters:    * doublecheck   If True, all files will be checked. If False (default), all files with
                                        a 'skip' flag will not be looked at again.
    """
    def update_entries(self, doublecheck=False):
        print("=> update_entries(doublecheck={})".format(doublecheck))
        time_update_start = time.time()
        try:
            with open(self.path_skipped_folders) as folder_file:
                temp = folder_file.read().splitlines()
                folders = []
                for entry in temp:
                    if entry[-1:] != "\\" and entry[-1:] != "/":
                        entry = entry + "\\"
                    folders.append(self.slash(entry))
                self.skipped_folders = folders
        except FileNotFoundError:
            print("There is no skipped_folder file at {}. Please correct the path.".format(self.path_skipped_folders))

        try:
            with open(self.path_skipped_extensions) as extension_file:
                extensions = extension_file.read().splitlines()
                self.skipped_extensions = extensions
        except FileNotFoundError:
            print("There is no skipped_extensions file at {}. Please correct the path.".format(self.path_skipped_extensions))

        def skipped_folder(path):
            path = self.slash(path) + "/"
            for entry in self.skipped_folders:
                entry = self.slash(entry)
                if path.startswith(entry) or path == entry:
                    return True
            return False

        total = 0
        non_existent = 0
        processed = 0
        skipped = 0

        for file in self.fileserver:
            total += 1
            if total % 1000 == 0:
                print("* still updating, currently at file {}...".format(total))

            file_skipped = self.fileserver[file]['skip']
            file_found = self.fileserver[file]['still_there']
            file_path = self.fileserver[file]['path']
            file_extension = self.fileserver[file]['extension']

            # in case there shan't be a doublecheck, skip file
            if not doublecheck:
                if file_skipped:
                    skipped += 1
                    continue

            # in case there is no doublecheck skip removed items
            if not doublecheck and not file_found:
                non_existent += 1
                continue

            # skip JPG if corresponding TIFF is available
            if file_extension == "jpg" or file_extension == "jpeg":
                path_stem = file[:file.rfind(".") + 1]
                if path_stem + "tif" in self.fileserver or path_stem + "tiff" in self.fileserver:
                    self.fileserver[file]['skip'] = True
                    continue

            # skip file if in skipped folder or has skipped extension
            if skipped_folder(file_path) or file_extension in self.skipped_extensions:
                self.fileserver[file]['skip'] = True
            elif self.fileserver[file]['name'].startswith("."):
                # skip all invisible files (starting with a .)
                self.fileserver[file]['skip'] = True
            else:
                self.fileserver[file]['skip'] = False

            # flag for all files whether they are still in place
            if os.path.isfile(file):
                self.fileserver[file]['still_there'] = True
            else:
                self.fileserver[file]['still_there'] = False

            if self.fileserver[file]['skip']:
                skipped += 1
                print(str(total) + " - Skipped: " + file)
            if not self.fileserver[file]['still_there']:
                non_existent += 1
                print(str(total) + " - Not there: " + file)
            if self.fileserver[file]['processed']:
                processed += 1
                print(str(total) + " - Already processed: " + file)

            self.fileserver[file]['db_entries'] = self.extract_db_connection(file)

        self.save_json()
        uploadable = total - skipped - non_existent
        time_update = time.time() - time_update_start

        print("Update finished! (doublecheck: {0}, {1:.2f}s)".format(doublecheck, time_update))
        print("{} files in total.".format(total))
        print("{} files were marked to be skipped for upload.".format(skipped))
        print("{} files cannot be found.".format(non_existent))
        print("----")
        print("{} files remain to be uploaded.".format(uploadable))

    """
        @description:   This method saves the current state of the JSON object to the hard disk. 
    """
    def save_json(self, alternative_path=""):
        print("=> save_json({})".format(alternative_path))
        if alternative_path == "":
            path = self.path_storage
        else:
            path = r"" + alternative_path

        file_ext_number = 1
        path = self.slash(path)

        # backup old file
        not_moved = True # True until a free number has been found and old JSON been saved to

        # create archive directory if necessary
        if not os.path.isdir(path + "archive/"):
            os.makedirs(path + "archive/")

        while not_moved:
            if os.path.isfile(path + "/archive/" + self.json_fileserver + "_" + str(file_ext_number) + ".txt"):
                file_ext_number += 1
                continue
            else:
                try:
                    old_path = path + self.json_fileserver + ".txt"
                    new_path = path + "/archive/" + self.json_fileserver + "_" + str(file_ext_number) + ".txt"
                    os.rename(old_path, new_path)
                    not_moved = False
                except FileNotFoundError:
                    not_moved = False

        # create new file
        with open(path + self.json_fileserver + ".txt", "w") as outfile:
            json.dump(self.fileserver, outfile)

    """
        @description:   This method loads an already stored JSON-file. If no JSON file is available
                        at the specified location, a new registering takes place.
                        
        @return:        [Dict] Returns the dictionary contained in the Fileserver JSON (or, if not
                        available, a new one).
    """
    def load_json(self, alternative_path=""):
        print("=> load_json({})".format(alternative_path))
        if alternative_path == "":
            path = r"./storage/" + self.json_fileserver + ".txt"
        else:
            path = r"" + alternative_path
        path = self.slash(path)

        try:
            with open(path) as json_file:
                data = json.load(json_file)
                print("Fileserver JSON has been successfully loaded.")
                self.fileserver = data
        except FileNotFoundError:
            print("No file has been found at {}. A new file will be created.".format(path))
            self.register_files()
            self.save_json()

    """
        @description:   This method simply changes all slash characters such that URLs are
                        formatted in the same way.
                        
        @return:        [String] Returns the re-formatted string.
    """
    def slash(self, string):
        result = string.replace(r"\\", "/")
        result = result.replace("\\", "/")
        return result

    def extract_db_connection(self, path_and_file_name):
        def add_value(dictionary, value, key):
            if key not in dictionary:
                dictionary[key] = []
            if not value in dictionary[key]:
                dictionary[key].append(value)
            return 1

        def get_regex_findall(regex, string, ignorecase=True):
            if ignorecase:
                regex_compiled = re.compile(regex, re.IGNORECASE)
            else:
                regex_compiled = re.compile(regex)

            findall = re.findall(regex_compiled, string)

            result = None
            if findall:
                result = findall[0][0]

            if result:
                return result
            else:
                return None

        def get_regex_match(regex, string, ignorecase=True):
            if ignorecase:
                regex_compiled = re.compile(regex, re.IGNORECASE)
            else:
                regex_compiled = re.compile(regex)

            match = re.match(regex_compiled, string)
            result = None
            if match:
                result = match.group(0)

            if result:
                return result
            else:
                return None

        def contains_au(string):
            regex_au = r"(AU\d+)"

            au = get_regex_match(regex_au, string)

            if au:
                if au.startswith("AU"):
                    au = au[2:]
                return au
            else:
                return False

        def contains_field_number(string):
            regex_field = r"(\b(AU)?\d{1,5}_V?\d+\b)"

            if get_regex_match(regex_field, string):
                return get_regex_match(regex_field, string)
            else:
                return False

        def contains_find(string):
            regex_ab = r"(\bAB\d+(\.\d+)?\b)"
            regex_c = r"\b(C\d+[a-z]?)"
            regex_chest = r"(\bCHEST\d+\b)"
            regex_mask = r"(\bMASK\d+\b)"
            regex_jackal = r"(\bJackal\d+\b)"
            regex_co = r"(\bCO\d+(\.\d+)?\b)"
            regex_w = r"(\bW\d+(\.\d+)?[a-z]?\b)"
            regex_u = r"(\bUI+\d*x?R?[a-z]?)"
            regex_dm = r"(\bDM\d+\b)"
            regex_mi = r"(\bMI\d+\b)"
            regex_fn = r"(\bFN\d+[\.]?\d{0,2}([a-z]([-|+][a-z])*)?)"
            regex_t = r"(\bT\d+\b)"
            regex_jde = r"(\bJD?E\d+\D{0,2}\b)"
            regex_dn = r"(\bDN\d+(\.\d+)?\b)"
            regex_cone = r"(\bCONE\d+(\.\d+)?\b)"

            if get_regex_match(regex_ab, string):
                return get_regex_match(regex_ab, string)
            elif get_regex_match(regex_c, string):
                return get_regex_match(regex_c, string)
            elif get_regex_match(regex_chest, string):
                return get_regex_match(regex_chest, string)
            elif get_regex_match(regex_mask, string):
                return get_regex_match(regex_mask, string)
            elif get_regex_match(regex_jackal, string):
                return get_regex_match(regex_jackal, string)
            elif get_regex_match(regex_jde, string):
                return get_regex_match(regex_jde, string)
            elif get_regex_match(regex_co, string):
                return get_regex_match(regex_co, string)
            elif get_regex_match(regex_w, string):
                return get_regex_match(regex_w, string)
            elif get_regex_match(regex_u, string):
                return get_regex_match(regex_u, string)
            elif get_regex_match(regex_dm, string):
                return get_regex_match(regex_dm, string)
            elif get_regex_match(regex_mi, string):
                return get_regex_match(regex_mi, string)
            elif get_regex_match(regex_fn, string):
                return get_regex_findall(regex_fn, string, False)
            elif get_regex_match(regex_t, string):
                return get_regex_match(regex_t, string)
            elif get_regex_match(regex_dn, string):
                return get_regex_match(regex_dn, string)
            elif get_regex_match(regex_cone, string):
                return get_regex_match(regex_cone, string)
            else:
                return False

        def contains_planum(string):
            regex_planum = r"(\b(AU)?\d+PL\d+(\.\d+)?\b)"

            if get_regex_match(regex_planum, string):
                planum = get_regex_match(regex_planum, string)
                if planum.startswith("AU"):
                    planum = planum[2:]
                return planum
            else:
                return False

        def contains_profile(string):
            regex_profile = r"(\b(AU)?\d+PR\d+\b)"

            if get_regex_match(regex_profile, string):
                profile = get_regex_match(regex_profile, string)
                if profile.startswith("AU"):
                    profile = profile[2:]
                return profile
            else:
                return False

        def contains_su(string):
            regex_su = r"(\bPL\d+-\d+)"

            if get_regex_match(regex_su, string):
                return get_regex_match(regex_su, string)
            else:
                return False

        def contains_zo(string):
            regex_zo = r"(\bZO\d+\b)"
            regex_zs = r"(\bZS\\d+[a-z]?(\.\d+[a-z]?)?)"
            regex_zp = r"(\bZP\d+[a-z]?(\.\d+[a-z]?)?)"
            regex_zk = r"(\bZK[S|C]?\d+[a-z]?(\.\d+[a-z]?)?)"

            if get_regex_match(regex_zo, string):
                return get_regex_match(regex_zo, string)
            elif get_regex_match(regex_zs, string):
                return get_regex_match(regex_zs, string)
            elif get_regex_match(regex_zp, string):
                return get_regex_match(regex_zp, string)
            elif get_regex_match(regex_zk, string):
                return get_regex_match(regex_zk, string)
            else:
                return False

        def contains_tomb(string):
            regex_tomb = r"(\b(TT|K)\d+[a-c]?|95[a-c])"

            tomb_concordance = {
                "k85": "1",
                "k453": "100",
                "k90": "500",
                "k555": "2000",
                "tt84": "6500",
                "tt95": "10000",
                "95a": "10010",
                "tt95a": "10010",
                "95b": "10003",
                "tt95b": "10003",
                "95c": "10004",
                "tt95c": "10004"
            }

            tomb = get_regex_match(regex_tomb, string)

            if tomb:
                tomb = tomb.lower()
                if tomb in tomb_concordance:
                    tomb = tomb_concordance[tomb]
                return tomb.upper()
            else:
                return False

        keys = {}

        path = self.slash(path_and_file_name)
        path = path.replace("/", " ")

        components = path.split(' ')

        for component in components:
            if contains_au(component):
                add_value(keys, contains_au(component), 'AU')
            if contains_field_number(component):
                add_value(keys, contains_field_number(component), 'FieldNumber')
            if contains_find(component):
                add_value(keys, contains_find(component), 'Find')
            if contains_planum(component):
                add_value(keys, contains_planum(component), 'Planum')
            if contains_profile(component):
                add_value(keys, contains_profile(component), 'Profile')
            if contains_su(component):
                add_value(keys, contains_su(component), 'SU')
            if contains_zo(component):
                add_value(keys, contains_zo(component), 'ZO')
            if contains_tomb(component):
                add_value(keys, contains_tomb(component), 'Tomb')

        return keys

    """
        @description:   This method prints to the console a set containing all extensions of the files
                        which should be uploaded, including their respective amount.
    """
    def get_all_extensions(self):
        print("=> get_all_extensions()")
        if self.fileserver:
            extensions = {}
            skipped_extensions= {}
            used_extensions = {}

            def add_extension(extension, set):
                if extension in set:
                    set[extension] += 1
                else:
                    set[extension] = 1

            for file in self.fileserver:
                extension = self.fileserver[file]['extension'].lower()
                skipped = self.fileserver[file]['skip']
                file_found = self.fileserver[file]['still_there']

                add_extension(extension, extensions)

                if skipped or not file_found:
                    add_extension(extension, skipped_extensions)
                else:
                    add_extension(extension, used_extensions)
            #print("Following extensions were found:")
            #pprint(extensions)
            #print("Skipped Extensions:")
            #pprint(skipped_extensions)
            print("Used Extensions:")
            pprint(used_extensions)
        else:
            print("There are currently no files registered. Please reload the existing file or re-register"
                  "the files on the fileserver.")

    """
        @description:   This method prints to the console all files including their path which are
                        registered with the specified file type extension.
                        
        @parameters:    * extension [String] - the extension for which files should be printed
                        * print_skipped [bool, default=False] - if True, then all files with the
                            specified extension are printed; if False (default), then only those
                            files will be printed which are destined for upload
    """
    def get_files_by_extension(self, extension, print_skipped=False):
        for file in self.fileserver:
            skipped = self.fileserver[file]['skip'] or not self.fileserver[file]['still_there']
            if skipped and not print_skipped:
                continue
            if self.fileserver[file]['extension'] == extension.lower():
                print(file)

    def get_files_without_db_connection(self, print_skipped=False):
        print("=> get_files_without_db_connection(print_skipped={}".format(print_skipped))
        total = 0
        for file in self.fileserver:
            skipped = self.fileserver[file]['skip']
            file_found = self.fileserver[file]['still_there']
            if not print_skipped:
                if skipped or not file_found:
                    continue
            if 'db_entries' not in self.fileserver[file] or not self.fileserver[file]['db_entries']:
                print(file)
                total += 1
        print("{} files have no database connection.".format(total))

    def get_unassigned_files(self, print_skipped=False):
        print("=> get_unassigned_files(print_skipped={}".format(print_skipped))
        total = 0
        set_unassigned_files = []
        for file in self.fileserver:
            skipped = self.fileserver[file]['skip']
            file_found = self.fileserver[file]['still_there']
            if not print_skipped:
                if skipped or not file_found:
                    continue

            no_db_connection = False
            no_package_connection = False

            if 'db_entries' not in self.fileserver[file] or not self.fileserver[file]['db_entries']:
                no_db_connection = True
            if 'packages' not in self.fileserver[file]:
                no_package_connection = True

            if no_db_connection and no_package_connection:
                total += 1
                set_unassigned_files.append(file)
                print(file)
        print("{} files have no database connection and are not part of any package.".format(total))
        return set_unassigned_files.sort()

    def get_unassigned_folders(self, print_skipped=False):
        print("=> get_unassigned_folders(print_skipped={}".format(print_skipped))
        paths = []
        for file in self.fileserver:
            skipped = self.fileserver[file]['skip']
            file_found = self.fileserver[file]['still_there']
            if not print_skipped:
                if skipped or not file_found:
                    continue

            no_db_connection = False
            no_package_connection = False

            if 'db_entries' not in self.fileserver[file] or not self.fileserver[file]['db_entries']:
                no_db_connection = True
            if 'packages' not in self.fileserver[file]:
                no_package_connection = True

            if no_db_connection and no_package_connection:
                if self.fileserver[file]['path'] not in paths:
                    paths.append(self.fileserver[file]['path'])

        paths.sort()
        for path in paths:
            print(path)
        print("Files in {} folders have no database connection and are not part of any package.".format(len(paths)))
        return paths

    """
        @description:   This method adds a flag for the specified package to all files in the specified folder.
                        The idea is that all files which belong to a specific set, like photogrammetric images
                        or diary photos, can easily be identified as such. These groups are usually not determined
                        by names or paths, but have to be manually assigned.
        
        @parameters:    * path_to_folder [String] - Path to the destined folder.
                        * package_name [String] - Name of the package
                        * recursive [bool] - if True, then all files in this folder and all subfolders are added
                                             to the package; if False, then only this particular folder is taken
                                             into account.
    """
    def add_folder_to_package(self, path_to_folder, package_name, recursive):
        print("=> add_folder_to_package(folder: {}, package_name: {}, recursive: {})".format(path_to_folder, package_name.lower(), recursive))
        total = 0
        for file in self.fileserver:
            file_path = self.fileserver[file]['path']

            # skip file if it's not in the right place
            if recursive:
                if not file_path.startswith(self.slash(path_to_folder)):
                    continue
            else:
                if not file_path == self.slash(path_to_folder):
                    continue

            # if package set does not yet exist, create it
            if 'packages' not in self.fileserver[file]:
                self.fileserver[file]['packages'] = []

            if package_name.lower() not in self.fileserver[file]['packages']:
                self.fileserver[file]['packages'].append(package_name.lower())
                total += 1

        print("Successfully added package {0} to {1} files.".format(package_name.lower(), total))

    """
        @description:   This method returns all files which have been added to a specific
                        package of files.
                        
        @parameters:    * package_name [String] - Name of the package the user is looking for.
                        * print_skipped [Bool] - if False (default), files which have been marked
                                                    as skipped are not printed. If true, these
                                                    entries will be printed.
    """
    def get_files_by_package(self, package_name, print_skipped=False):
        total = 0
        for file in self.fileserver:
            skipped = self.fileserver[file]['skip']
            file_found = self.fileserver[file]['still_there']

            if skipped and not print_skipped:
                continue
            if not file_found:
                continue
            if 'packages' not in self.fileserver[file]:
                continue

            if package_name.lower() in self.fileserver[file]['packages']:
                total += 1
                print(file)

        print("{0} files have been found for package {1}.".format(total, package_name.lower()))

    """
        @description:   This method returns all packages which have been added to the data.
    """
    def get_list_of_packages(self):
        packages = []
        for file in self.fileserver:
            if 'packages' not in self.fileserver[file]:
                continue

            for package in self.fileserver[file]['packages']:
                if package not in packages:
                    packages.append(package)

        print(packages)
        print("{} different packages have been found.".format(len(packages)))

    """
        @description:   This method removes all entries from the dictionary which are flagged as
                        not existent on the fileserver anymore. Their entry "still_there" is set
                        to False during the update_entries procedure.
    """
    def remove_lost_files(self):
        print("=> remove_lost_files()")

        deletable_entries = []

        for file in self.fileserver:
            if not self.fileserver[file]['still_there']:
                deletable_entries.append(file)

        for entry in deletable_entries:
            del self.fileserver[entry]

        self.save_json()

    """
        @description:   Simple method which simply counts all the flags available for the data entries.
    """
    def get_numbers(self):
        print("=> get_numbers()")
        counter_skipped = 0
        counter_lost = 0
        counter_processed = 0
        counter_total = 0

        for file in self.fileserver:
            counter_total += 1
            if self.fileserver[file]['skip']:
                counter_skipped += 1
            if not self.fileserver[file]['still_there']:
                counter_lost += 1
            if self.fileserver[file]['processed']:
                counter_processed += 1

        print("Aggregation of numbers has finished:")
        print("- Elements in total: {}".format(counter_total))
        print("- Elements skipped: {}   -   unskipped: {}".format(counter_skipped, counter_total-counter_skipped))
        print("- Elements lost: {}   -   still there: {}".format(counter_lost, counter_total-counter_lost))
        print("- Elements processed: {}   -   unprocessed: {}".format(counter_processed, counter_total-counter_processed-counter_skipped-counter_lost
                                                                      ))

    def test_string(self, string):
        print("=> test_string(string='{}')".format(string))
        result = self.extract_db_connection(string)
        print(result)