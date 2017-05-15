import subprocess
import re


class ZabbixSenderException(Exception):
    pass


class ZabbixSender(object):
    def __init__(self, sender_path, config_path):
        self.r_processed = re.compile('processed: (\d+);')
        self.r_failed = re.compile('failed: (\d+);')
        self.r_total = re.compile('total: (\d+);')
        self.sender_path = sender_path
        self.config_path = config_path

        self.last_command = None

    def _execute_sender(self, arguments):
        self.last_command = [self.sender_path, '-c', self.config_path] + arguments
        output, error = subprocess.Popen(self.last_command, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE).communicate()
        if error: raise ZabbixSenderException(error)

        return output

    def _parse_output(self, output):
        processed_item_count = int(self.r_processed.search(str(output)).group(1))
        failed_item_count = int(self.r_failed.search(str(output)).group(1))
        total_item_count = int(self.r_total.search(str(output)).group(1))

        if failed_item_count:
            raise ZabbixSenderException('%i failed Items during %s' % (failed_item_count, self.last_command))
        if processed_item_count != total_item_count:
            raise ZabbixSenderException('Missmatching: %i != %i' % (processed_item_count, total_item_count))

    def send_item(self, name, value):
        self._parse_output(self._execute_sender(['-k', name, '-o', '%s' % value]))

        return '%s: %s' % (name, value)


class GpuStats(object):
    def __init__(self, eth_hashrate, temperature=None, fan_speed=None):
        self.eth_hashrate = eth_hashrate
        self.temperature = temperature
        self.fan_speed = fan_speed


class ClaymoreMinerStats(object):
    def __init__(self, json):
        self.version, runs_for_minutes, eth_mining_stats, eth_hashrates, dcr_mining_stats, dcr_hashrates, gpu_stats, \
        self.mining_pool, share_stats = json['result']

        eth_hashrates = eth_hashrates.split(';')
        stats = gpu_stats.split(';')
        if len(stats): assert (len(stats) == len(eth_hashrates) * 2)

        self.gpus = []
        for i, hashrate in enumerate(eth_hashrates):
            if stats:
                temperature = stats[i * 2]
                fan_speed = stats[i * 2 + 1]
                self.gpus.append(GpuStats(hashrate, temperature, fan_speed))
            else:
                self.gpus.append(GpuStats(hashrate))

        self.runs_for_minutes = int(runs_for_minutes)

        spl = eth_mining_stats.split(';')
        self.total_hashrate = int(spl[0])
        self.total_shares = int(spl[1])
        self.total_rejected_shares = int(spl[2])

        spl = share_stats.split(';')
        self.incorrect_shares = int(spl[0])
