from datetime import datetime
import time
import os
from xml.dom.minidom import parse
import xml.dom.minidom
import socket
import subprocess
import shutil

from revitfarm.plugin.base.jobhandler import AbstractJobTaskSequencesGenerator, AbstractJobStartHandler, \
    AbstractJobCompleteHandler, AbstractJobTaskSequenceRunner, \
    AbstractJobWorkerStartHandler, AbstractJobWorkerCompleteHandler
from revitfarm.job.data.task import TaskSequence, Task
from revitfarm.job.data.taskresult import TaskResult, TaskResultTypes
from revitfarm.core.util.const import Const



ADSK_DEV_HOME = os.environ['ADSK_DEV_HOME']
IWD_LOCAL_REPO_DIR = "{}\\infraworks-desktop".format(ADSK_DEV_HOME)
IWD_RUNTIME_HOME_DIR = "{}\\runtime".format(ADSK_DEV_HOME)
IWD_LOCAL_QA_HOME_DIR = "{}\\Test".format(IWD_LOCAL_REPO_DIR)
IWD_LOCAL_QA_ENV_DIR = "{}\\env\\aim".format(IWD_LOCAL_QA_HOME_DIR)
IWD_LOCAL_JS_DIR = "{}\\API\\aim\\tests\\javascript".format(IWD_LOCAL_QA_HOME_DIR)
IWD_UT_RESULT_DIR = "{}\\aim\\UnitTest\\results".format(IWD_RUNTIME_HOME_DIR)
IWD_RUNTIME_API_DIR = "{}\\aim\\API\\tests\\javascript".format(IWD_RUNTIME_HOME_DIR)


def get_now_epoch():
     return (int(time.mktime(datetime.now().timetuple())))

def runBat(cmd):
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (result, error) = process.communicate()
    rc = process.wait()
    if rc != 0:
        print("Error: failed to execute command:", cmd)
        print(error)
    return rc


class JobTaskSequencesGenerator(AbstractJobTaskSequencesGenerator):
    def __init__(self, job_folder_on_submitter, job_config_data):
        super().__init__(job_folder_on_submitter, job_config_data)

    def parse_xml_to_ist(self, test_xml_file):
        tc_list = []
        try:
            tree = xml.dom.minidom.parse(test_xml_file)
            data = tree.documentElement
        except Exception:
            print("Error parse file")
            self.logger.error("Failed to parse xml file {}".format(test_xml_file))
        for feature_type in ["IW-API", "IW-UT"]:
            api_tag = "0"
            if feature_type != "IW-API": api_tag = "1"
            for iw_api_ut in data.getElementsByTagName(feature_type):
                for feature in iw_api_ut.getElementsByTagName('Feature'):
                    feature_name = feature.getAttribute("Name")
                    testCases = feature.getAttribute("TestCases")
                    tc_list.append(api_tag + feature_name + "-" + testCases)
        return tc_list

    def generate_task_sequences(self):
        self.logger.info("Generate task sequances")
        test_xml_file = self.job_config_data.get("module", {}).get("params", {}).get("test_xml_file")
        if test_xml_file is None or not os.path.isfile(test_xml_file):
            self.logger.error("{} is not a valid file path.".format(test_xml_file))

        test_list = self.parse_xml_to_ist(test_xml_file)
        if len(test_list) == 0:
            self.logger.error("There is no item in test_list!")
        else:
            for task_sequence_index in range(0, len(test_list)):
                yield TaskSequence(
                    sequence_id=task_sequence_index,
                    tasks=[
                        Task(name="{}".format(test_list[task_sequence_index]),
                             task_sequence_index=task_sequence_index, task_index=0)
                    ]
                )

class JobWorkerStartHandler(AbstractJobWorkerStartHandler):
    def __init__(self, job_worker_context):
        super().__init__(job_worker_context)

    def on_start(self, status_update_callback):
        status = "Job {} is starting in worker {} now.".format(self.job_context.job_name, os.getpid())
        self.logger.info(status)
        status = "Sync IWD code..."
        self.logger.info(status)
        ghprbPullId=self.job_context.job_config.get("module",{}).get("params", {}).get("ghprbPullId", {})
        ghprbActualCommit = self.job_context.job_config.get("module", {}).get("params", {}).get("ghprbActualCommit", {})
        buildName = "PR#{}-{}".format(ghprbPullId, ghprbActualCommit)
        IWD_INSTALL_DIR = "C:\\{}".format(buildName)
        packagePath = self.job_context.job_config.get("module", {}).get("params", {}).get("packagePath", {})
        packageName = "PR_{}.zip".format(ghprbPullId)

        #fetch_iwd_gitsrc_cmd="cd /d c:\gitroot\infraworks-desktop & git init & git remote add origin https://git.autodesk.com/InfraWorks/infraworks-desktop.git &  git fetch origin master &git fetch --tags --progress https://git.autodesk.com/InfraWorks/infraworks-desktop.git +refs/pull/*:refs/remotes/origin/pr/*"
        if not os.path.exists(IWD_LOCAL_REPO_DIR):
            mkiwddir=os.system("mkdir {}".format(IWD_LOCAL_REPO_DIR))
            self.logger.info("make directory infraworks-desktop status is {}".format(mkiwddir))
        #fetch_status = runBat(fetch_iwd_gitsrc_cmd)
        #update_tools="cd /d {}&call UpdateAutomationTools.bat".format(IWD_LOCAL_QA_HOME_DIR)
        #runBat(update_tools)
        fetch_status = 0
        if(fetch_status==0):
            self.logger.info("Sync infraworks-desktop successfully!")
        else:
            self.logger.info("Sync failed! sync infraworks-desktop status is {}".format(fetch_status))

        status = "Stub installer..."
        self.logger.info(status)
        os.system("net use \\\\ussclpdfsmpn011 /user:ads\\mapuser 01gisqa!")
        dirs_in_c = os.listdir("c:\\")
        for it in dirs_in_c:
            if "PR#" in it:
                print(it)
                shutil.rmtree(os.path.join("c:\\", it))
        stub_install_cmd="cd /d {}\\utils& set PATH={}\\tools\Python64;%PATH% &call setenv.cmd >nul&robocopy {} {} {}&call ant unzipfiles -Dsrc=\"{}\\{}\" -Ddest={}&cd /d {}&call InstallPackageBuild.bat".\
            format(IWD_LOCAL_QA_HOME_DIR, IWD_LOCAL_QA_HOME_DIR, packagePath, IWD_INSTALL_DIR, packageName, IWD_INSTALL_DIR, packageName, IWD_INSTALL_DIR, IWD_INSTALL_DIR)
        stub_install_status=runBat(stub_install_cmd)
        self.logger.info("local package is {}, packageName is {}, stubinstaller return status is {}".format(IWD_INSTALL_DIR, packageName,stub_install_status))

        status = "Cleanup api test result folder..."
        self.logger.info(status)
        if os.path.isdir(IWD_RUNTIME_API_DIR):
            cleanup_api_folder = "rd {} /Q /S".format(IWD_RUNTIME_API_DIR)
            cleanup_resultfolder_status = runBat(cleanup_api_folder)
            self.logger.info("Cleanup result folder result is {}, result folder is {}.".format(cleanup_resultfolder_status, IWD_RUNTIME_API_DIR))

        status = "Prepare test data..."
        self.logger.info(status)
        prepare_cmd="cd /d {}& set PATH={}\\tools\Python64;%PATH% &call setenv.cmd {} >nul&cd /d {}&call ant authenticateToNearestContentProvider&call taskkill /T /F /IM adappmgr.exe&rd {} /Q /S&call ant cleanResultsDir&call ant changeReg -DcloudService=\"Dev\"&cd /d {}\\UnitTest&call ant cleanunittestXMLResultHome -DunitTestXMLResultHome={}".\
            format(IWD_LOCAL_QA_ENV_DIR, IWD_LOCAL_QA_HOME_DIR, IWD_INSTALL_DIR, IWD_LOCAL_JS_DIR, IWD_RUNTIME_API_DIR, IWD_LOCAL_QA_HOME_DIR, IWD_UT_RESULT_DIR)
        prepare_data_status=runBat(prepare_cmd)
        self.logger.info("prepare test data status is {}".format(prepare_data_status))
        return True

class JobTaskSequenceRunner(AbstractJobTaskSequenceRunner):
    buildName = None
    IWD_INSTALL_DIR = None

    def __init__(self, job_worker_context):
        super().__init__(job_worker_context)

    def on_task_sequence_start(self, task_sequence_index, status_update_callback):
        status = "Running into task sequence start..."
        self.logger.info(status)
        status_update_callback(status)
        ghprbPullId = self.job_context.job_config.get("module", {}).get("params", {}).get("ghprbPullId", {})
        ghprbActualCommit = self.job_context.job_config.get("module", {}).get("params", {}).get("ghprbActualCommit", {})
        self.buildName = "PR#{}-{}".format(ghprbPullId, ghprbActualCommit)
        self.IWD_INSTALL_DIR = "C:\\{}".format(self.buildName)

    def on_task_sequence_complete(self, task_sequence_index, status_update_callback):
        status = "Running into task sequence complete, archive and upload results..."
        status_update_callback(status)
        result_src = "{}\\results".format(IWD_RUNTIME_API_DIR)
        archive_cmd = "cd /d {} & set PATH={}\\tools\Python64;%PATH% & call setenv.cmd {} >nul & cd /d {} & call ant archiveJavascriptResults -DbuildNumber={} -DsuiteName=\"Full_Regression\" -DaimProjectName=\"InfraWorks_FarmTest_R18.2\" -DaimProductTitle=\"Autodesk Infraworks Rolling Sandbox\"".\
            format(IWD_LOCAL_QA_ENV_DIR, IWD_LOCAL_QA_HOME_DIR, self.IWD_INSTALL_DIR, IWD_LOCAL_JS_DIR, self.buildName.replace('#', ''))
        upload_cmd = "cd /d {} & set PATH={}\\tools\Python64;%PATH% & call setenv.cmd {} >nul & cd /d {} & call ant uploadJavascriptResults -DbuildNumber={} -DsuiteName=\"Full_Regression\" -DaimProjectName=\"InfraWorks_FarmTest_R18.2\" -DaimProductTitle=\"Autodesk Infraworks Rolling Sandbox\" -DfromArchive=\"AnyValueWorks\"". \
            format(IWD_LOCAL_QA_ENV_DIR, IWD_LOCAL_QA_HOME_DIR, self.IWD_INSTALL_DIR, IWD_LOCAL_JS_DIR, self.buildName.replace('#', ''))
        if os.path.isdir(result_src):
            archive_status = runBat(archive_cmd)
            upload_status = runBat(upload_cmd)
            self.logger.info("Archive result files status is {}, upload result status is {}.".format(archive_status, upload_status))
        else:
            self.logger.info("No test result files generated at {}! Skip archive and upload!".format(result_src))


    def run_task(self, task_sequence, task_index):
        try:
            status = "Running into task sequence running..."
            self.logger.info(status)
            task = task_sequence.tasks[task_index]
            task_name = task.name.strip()
            task_name_split = task_name.split('-')
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            st_time = get_now_epoch()
            self.logger.info("Current task feature folder is {}, test cases list is {}."
                             .format(task_name_split[0].strip('0').strip('1'), task_name_split[1]))
            if task_name_split[0].startswith('0'):       # API
                if(len(task_name_split[1])==0):
                    run_cmd = "cd /d {} & set PATH={}\\tools\Python64;%PATH% & call setenv.cmd {} >nul & cd /d {} & call ant AdLogin & cd {}\\{} & call ant runtests -DcomponentFileAlreadyExists=true -DenableRerun=true". \
                        format(IWD_LOCAL_QA_ENV_DIR, IWD_LOCAL_QA_HOME_DIR, self.IWD_INSTALL_DIR, IWD_LOCAL_JS_DIR, IWD_LOCAL_JS_DIR, task_name_split[0].strip('0'))
                else:
                    run_cmd = "cd /d {} & set PATH={}\\tools\Python64;%PATH% & call setenv.cmd {} >nul & cd /d {} & call ant AdLogin & cd {}\\{} & call ant runtests -DtestList=\"{}\" -DcomponentFileAlreadyExists=true -DenableRerun=true".\
                        format(IWD_LOCAL_QA_ENV_DIR, IWD_LOCAL_QA_HOME_DIR, self.IWD_INSTALL_DIR, IWD_LOCAL_JS_DIR, IWD_LOCAL_JS_DIR, task_name_split[0].strip('0'), task_name_split[1])
            elif task_name_split[0].startswith('1'):         # UT
                run_cmd = "{}\\{} {}.replace(',',' ') ~[skip] -o {}\\{}[0..-5].xml -r junit-thread-safe --parallel 8".\
                    format(self.IWD_INSTALL_DIR, task_name_split[0].strip('1'), task_name_split[1], IWD_UT_RESULT_DIR, task_name_split[0].strip('1'))
            else:
                run_cmd = None
                self.logger.error("Error mode: {}, it is not API or UT.".format(task_name_split[0]))

            result_code = runBat(run_cmd)
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            ed_time = get_now_epoch()
            self.logger.info("The return code of run cmd is {}".format(repr(result_code)))
            self.logger.info("Running test {}:{} for {} seconds".format(task.task_sequence_index,
                                                                        task.task_index, ed_time - st_time))
            result_type = TaskResultTypes.SUCCESS
            if result_code != 0:
                result_type = TaskResultTypes.FAILURE
            return TaskResult(task_sequence_index=task.task_sequence_index,
                                task_index=task.task_index,
                                result_type=result_type,
                                result_data={"node": socket.gethostname(), "start": start_time, "end": end_time})
        except Exception as ex:
            self.logger.error("Error occurred while running sequence {}".format(task_sequence.sequence_id))
            self.logger.error(ex)
            return TaskResult(task.task_sequence_index, task_index, TaskResultTypes.FAILURE,
                                   task_type=task_sequence.task_type, result_message=str(ex),
                                   result_data={"node": Const.LOCALHOST})
