import subprocess
from time import sleep

from htpclient.binarydownload import BinaryDownload
from htpclient.chunk import Chunk
from htpclient.files import Files
from htpclient.hashcat_cracker import HashcatCracker
from htpclient.hashlist import Hashlist
from htpclient.initialize import Initialize
from htpclient.jsonRequest import *
import logging

from htpclient.task import Task

CONFIG = None
binaryDownload = None


def init():
    global CONFIG, binaryDownload

    # TODO: fix logging style
    logging.basicConfig(filename='client.log', level=logging.DEBUG)
    urllib3_logger = logging.getLogger('urllib3')
    urllib3_logger.setLevel(logging.ERROR)
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.basicConfig(format='[%(asctime)s] %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    CONFIG = Config()
    # connection initialization
    Initialize().run()
    # download and updates
    binaryDownload = BinaryDownload()
    binaryDownload.run()


def loop():
    global binaryDownload, CONFIG

    # TODO: this loop is running on the agent
    logging.info("Entering loop...")
    task = Task()
    chunk = Chunk()
    files = Files()
    hashlist = Hashlist()
    task_change = True
    last_task_id = 0
    while True:
        if task.get_task() is not None:
            last_task_id = task.get_task()['taskId']
        task.load_task()
        if task.get_task() is None:
            task_change = True
            continue
        else:
            if task.get_task()['taskId'] is not last_task_id:
                task_change = True
        if not binaryDownload.check_version(task.get_task()['crackerId']):
            task_change = True
            continue
        if not files.check_files(task.get_task()['files'], task.get_task()['taskId']):
            task_change = True
            continue
        if task_change and not hashlist.load_hashlist(task.get_task()['hashlistId']):
            continue
        task_change = False
        logging.info("Got cracker binary type " + binaryDownload.get_version()['name'])
        chunk_resp = chunk.get_chunk(task.get_task()['taskId'])
        cracker = HashcatCracker(task.get_task()['crackerId'], binaryDownload)
        if chunk_resp == 0:
            task.reset_task()
            continue
        elif chunk_resp == -1:
            # measure keyspace
            cracker.measure_keyspace(task.get_task(), chunk)
            continue
        elif chunk_resp == -2:
            # measure benchmark
            result = cracker.run_benchmark(task.get_task())
            if result == 0:
                sleep(10)
                # some error must have occured on benchmarking
                continue
            # send result of benchmark
            req = JsonRequest(
                {'action': 'sendBenchmark', 'token': CONFIG.get_value('token'), 'taskId': task.get_task()['taskId'],
                 'type': 'run', 'result': result})
            ans = req.execute()
            if ans is None:
                logging.error("Failed to send benchmark!")
                sleep(5)
                continue
            elif ans['response'] != 'SUCCESS':
                logging.error("Error on sending benchmark: " + str(ans))
                sleep(5)
                continue
            else:
                logging.info("Server accepted benchmark!")
                continue
        # run
        logging.info("Start cracking...")
        cracker.run_chunk(task.get_task(), chunk.chunk_data())
        # Request Task
        # - Load cracker if needed
        # - Load Files
        # - Load Hashlist
        # - Request Chunk
        #   - Do Keyspace
        #   - Do Benchmark
        # - As long as there is no error, request more chunks


if __name__ == "__main__":
    init()
    loop()
