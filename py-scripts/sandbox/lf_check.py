#!/usr/bin/python3

'''
NAME:
lf_check.py

PURPOSE:
Configuration for lf_check.py , runs various tests

EXAMPLE:
lf_check.py

NOTES:

'''

import sys
if sys.version_info[0]  != 3:
    print("This script requires Python3")
    exit()

import os
import logging
import time
from time import sleep
import argparse
import json
from json import load
import configparser
from pprint import *
import subprocess
import sys
#from ..lf_report import lf_report
sys.path.append('../')
from lf_report import lf_report
sys.path.append('/')

CONFIG_FILE = os.getcwd() + '/lf_check_config.ini'    
RUN_CONDITION = 'ENABLE'

# see https://stackoverflow.com/a/13306095/11014343
class FileAdapter(object):
    def __init__(self, logger):
        self.logger = logger
    def write(self, data):
        # NOTE: data can be a partial line, multiple lines
        data = data.strip() # ignore leading/trailing whitespace
        if data: # non-blank
           self.logger.info(data)
    def flush(self):
        pass  # leave it to logging to flush properly

class lf_check():
    def __init__(self,
                _csv_outfile,
                _outfile):
        self.lf_mgr_ip = ""
        self.lf_mgr_port = "" 
        self.radio_dict = {}
        self.test_dict = {}
        path_parent = os.path.dirname(os.getcwd())
        os.chdir(path_parent)
        self.scripts_wd = os.getcwd()
        self.results = ""
        self.csv_outfile = _csv_outfile,
        self.outfile = _outfile
        self.test_result = "Failure"
        self.results_col_titles = ["Test","Command","Result","STDOUT","STDERR"]
        self.html_results = ""
        self.background_green = "background-color:green"
        self.background_red = "background-color:red"
        self.background_purple = "background-color:purple"

    def get_html_results(self):
        return self.html_results

    def start_html_results(self):
        self.html_results += """
                <table border="1" class="dataframe">
                    <thead>
                        <tr style="text-align: left;">
                          <th>Test</th>
                          <th>Command</th>
                          <th>Result</th>
                          <th>STDOUT</th>
                          <th>STDERR</th>
                        </tr>
                      </thead>
                      <tbody>
                      """

    def finish_html_results(self):
        self.html_results += """
                    </tbody>
                </table>
                <br>
                <br>
                <br>
                """

    # Functions in this section are/can be overridden by descendants
    def read_config_contents(self):
        print("read_config_contents {}".format(CONFIG_FILE))
        config_file = configparser.ConfigParser()
        success = True
        success = config_file.read(CONFIG_FILE)
        #print("{}".format(success))
        #print("{}".format(config_file))

        if 'LF_MGR' in config_file.sections():
            section = config_file['LF_MGR']
            self.lf_mgr_ip = section['LF_MGR_IP']
            self.lf_mgr_port = section['LF_MGR_PORT']
            print("lf_mgr_ip {}".format(self.lf_mgr_ip))
            print("lf_mgr_port {}".format(self.lf_mgr_port))

        if 'TEST_IP' in config_file.sections():
            section = config_file['TEST_IP']
            self.http_test_ip = section['HTTP_TEST_IP']
            print("http_test_ip {}".format(self.http_test_ip))
            self.ftp_test_ip = section['FTP_TEST_IP']
            print("ftp_test_ip {}".format(self.ftp_test_ip))
            
        # NOTE: this may need to be a list for ssi 
        if 'RADIO_DICTIONARY' in config_file.sections():
            section = config_file['RADIO_DICTIONARY']
            self.radio_dict = json.loads(section.get('RADIO_DICT', self.radio_dict))
            print("self.radio_dict {}".format(self.radio_dict))

        if 'TEST_DICTIONARY' in config_file.sections():
            section = config_file['TEST_DICTIONARY']
            # for json replace the \n and \r they are invalid json characters, allows for multiple line args 
            self.test_dict = json.loads(section.get('TEST_DICT', self.test_dict).replace('\n',' ').replace('\r',' '))
            #print("test_dict {}".format(self.test_dict))

    def load_factory_default_db(self):
        #print("file_wd {}".format(self.scripts_wd))
        try:
            os.chdir(self.scripts_wd)
            #print("Current Working Directory {}".format(os.getcwd()))
        except:
            print("failed to change to {}".format(self.scripts_wd))

        # no spaces after FACTORY_DFLT
        command = "./{} {}".format("scenario.py", "--load FACTORY_DFLT")
        process = subprocess.Popen((command).split(' '), shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        # wait for the process to terminate
        out, err = process.communicate()
        errcode = process.returncode

    # Not currently used
    def load_blank_db(self):
        #print("file_wd {}".format(self.scripts_wd))
        try:
            os.chdir(self.scripts_wd)
            #print("Current Working Directory {}".format(os.getcwd()))
        except:
            print("failed to change to {}".format(self.scripts_wd))

        # no spaces after FACTORY_DFLT
        command = "./{} {}".format("scenario.py", "--load BLANK")
        process = subprocess.Popen((command).split(' '), shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


    def run_script_test(self):
        self.start_html_results() 
        for test in self.test_dict:
            if self.test_dict[test]['enabled'] == "FALSE":
                print("test: {}  skipped".format(test))
            # load the default database 
            elif self.test_dict[test]['enabled'] == "TRUE":
                # loop through radios
                for radio in self.radio_dict:
                    # Replace RADIO, SSID, PASSWD, SECURITY with actual config values (e.g. RADIO_0_CFG to values)
                    # not "KEY" is just a word to refer to the RADIO define (e.g. RADIO_0_CFG) to get the vlaues
                    if self.radio_dict[radio]["KEY"] in self.test_dict[test]['args']:
                        self.test_dict[test]['args'] = self.test_dict[test]['args'].replace(self.radio_dict[radio]["KEY"],'--radio "{}" --ssid "{}" --passwd "{}" --security "{}"'
                        .format(self.radio_dict[radio]['RADIO'],self.radio_dict[radio]['SSID'],self.radio_dict[radio]['PASSWD'],self.radio_dict[radio]['SECURITY']))

                if 'HTTP_TEST_IP' in self.test_dict[test]['args']:
                    self.test_dict[test]['args'] = self.test_dict[test]['args'].replace('HTTP_TEST_IP',self.http_test_ip)
                if 'FTP_TEST_IP' in self.test_dict[test]['args']:
                    self.test_dict[test]['args'] = self.test_dict[test]['args'].replace('FTP_TEST_IP',self.ftp_test_ip)

                self.load_factory_default_db()
                sleep(5) # the sleep is to allow for the database to stablize

                # this is just to get the directory with the scripts to run. 
                #print("file_wd {}".format(self.scripts_wd))
                try:
                    os.chdir(self.scripts_wd)
                    #print("Current Working Directory {}".format(os.getcwd()))
                except:
                    print("failed to change to {}".format(self.scripts_wd))
                cmd_args = "{}".format(self.test_dict[test]['args'])
                command = "./{} {}".format(self.test_dict[test]['command'], cmd_args)
                print("command: {}".format(command))
                print("cmd_args {}".format(cmd_args))

                if self.outfile is not None:
                    stdout_log_txt = self.outfile
                    stdout_log_txt = stdout_log_txt + "-{}-stdout.txt".format(test)
                    #print("stdout_log_txt: {}".format(stdout_log_txt))
                    stdout_log = open(stdout_log_txt, 'a')
                    stderr_log_txt = self.outfile
                    stderr_log_txt = stderr_log_txt + "-{}-stderr.txt".format(test)                    
                    #print("stderr_log_txt: {}".format(stderr_log_txt))
                    stderr_log = open(stderr_log_txt, 'a')
                process = subprocess.Popen((command).split(' '), shell=False, stdout=stdout_log, stderr=stderr_log, universal_newlines=True)

                # close the file
                stdout_log.close()
                stderr_log.close()

                sleep(2)

                #print(stdout_log_txt)
                stdout_log_size = os.path.getsize(stdout_log_txt)
                stdout_log_size = os.stat(stdout_log_txt).st_size
                print("stdout_log_size {}".format(stdout_log_size))
                print("stdout {}".format(os.stat(stdout_log_txt)))
                #print(stderr_log_txt)
                stderr_log_size = os.path.getsize(stderr_log_txt)
                if stderr_log_size > 0 :
                    print("File: {} is not empty: {}".format(stderr_log_txt,str(stderr_log_size)))

                    self.test_result = "Failure"
                    background = self.background_red
                else:
                    print("File: {} is empty: {}".format(stderr_log_txt,str(stderr_log_size)))
                    self.test_result = "Success"
                    background = self.background_green


                self.html_results += """
                    <tr><td>""" + str(test) + """</td><td class='scriptdetails'>""" + str(command) + """</td>
                <td style="""+ str(background) + """>""" + str(self.test_result) + """ 
                <td><a href=""" + str(stdout_log_txt) + """ target=\"_blank\">STDOUT</a></td>"""
                if self.test_result == "Failure":
                    self.html_results += """<td><a href=""" + str(stderr_log_txt) + """ target=\"_blank\">STDERR</a></td>"""
                else:
                    self.html_results += """<td></td>"""
                self.html_results += """</tr>""" 
                # CMR need to generate the CSV.. should be pretty straight forward
                row = [test,command,self.test_result,stdout_log_txt,stderr_log_txt]
                #print("row: {}".format(row))
                print("test: {} executed".format(test))

            else:
                print("enable value {} invalid for test: {}, test skipped".format(self.test_dict[test]['enabled'],test))

        self.finish_html_results()        

def main():
    # arguments
    parser = argparse.ArgumentParser(
        prog='lf_check.py',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''\
            lf_check.py : for running scripts listed in lf_check_config.ini file
            ''',
        description='''\
lf_check.py
-----------

Summary :
---------
for running scripts listed in lf_check_config.ini
            ''')

    parser.add_argument('--outfile', help="--outfile <Output Generic Name>  used as base name for all files generated", default="")

    args = parser.parse_args()    

    # output report.
    report = lf_report(_results_dir_name = "lf_check",_output_html="lf_check.html",_output_pdf="lf-check.pdf")

    current_time = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
    csv_outfile = "lf_check{}-{}.csv".format(args.outfile,current_time)
    csv_outfile = report.file_add_path(csv_outfile)
    #print("csv output file : {}".format(csv_outfile))
    outfile = "lf_check-{}-{}".format(args.outfile,current_time)
    outfile = report.file_add_path(outfile)
    #print("output file : {}".format(outfile))

    # lf_check() class created
    check = lf_check(_csv_outfile = csv_outfile,
                    _outfile = outfile)

    # get the git sha 
    process = subprocess.Popen(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE)
    (commit_hash, err) = process.communicate()
    exit_code = process.wait()
    git_sha = commit_hash.decode('utf-8','ignore')
    #print("commit_hash: {}".format(commit_hash))
    #print("commit_hash2: {}".format(commit_hash.decode('utf-8','ignore')))


    check.read_config_contents() # CMR need mode to just print out the test config and not run 
    check.run_script_test()

    # Generate Ouptput reports
    report.set_title("LF Check: lf_check.py")
    report.build_banner()
    report.set_table_title("LF Check Test Results")
    report.build_table_title()
    report.set_text("git sha: {}".format(git_sha))
    report.build_text()
    html_results = check.get_html_results()
    #print("html_results {}".format(html_results))
    report.set_custom_html(html_results)
    report.build_custom()
    report.write_html_with_timestamp()
    report.write_pdf_with_timestamp()


if __name__ == '__main__':
    main()


