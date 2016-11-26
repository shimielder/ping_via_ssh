import paramiko
import re, time
import logging
from sys import argv
import concurrent.futures

exc_info = True
script_start_time = time.clock()
ping_result_pattern = re.compile('(\d+.\d+/\d+.\d+/\d+.\d+/\d+.\d+)')


class SSHClientExt(paramiko.SSHClient):
    def ping_exec(self, command):
        start_ping_time = time.clock()
        host = command.split(' ')[-1]
        logging.debug('Executing command: "{}"'.format(command))
        stdin, stdout, stderr = self.exec_command(command)
        data = stdout.read().decode('utf-8')

        data = data.rstrip('\n').rstrip(' ').split('\n')[-1]

        data_info = data.lstrip('rtt ')
        data = ping_result_pattern.search(data)

        logging.debug('Script execution time (ping {}): {} sec'.format(host, time.clock() - start_ping_time))
        if data:
            data = data.group()
            data = data.split('/')[1]

            return (data_info, float(data), host)
        else:
            logging.warning('Couldn\'t ping host: {}'.format(host))
            return (None, None, host)


def set_log_config(loglevel):
    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = 0
    return logging.basicConfig(format='[%(asctime)s]  %(message)s', level=numeric_level)


def adresses_loading(filename='config.txt'):
    logging.info('Opening file {}...'.format(filename))
    try:
        with open(filename, 'r') as config_file:
            adresses = []
            logging.info('Loading adresses...')
            for line in config_file:
                line = line.strip('\n')
                if not line or not line.strip(' '):
                    logging.debug('Skipping empty string...')
                    continue
                adresses.append(line.strip(' '))
                logging.debug('Appending IP adress: {}'.format(line))
            logging.info('Adresses loaded...')
        return adresses
    except FileNotFoundError:
        logging.error('Config file not found!')
    except Exception:
        logging.error('Something goes wrong:\n', exc_info=exc_info)


def getopts(argv):
    opts = {'-h': '',
            '-p': '',
            '-u': '',
            '-port': '22',
            '-f': 'config.txt',
            '-c': '5',
            '-e': 'utf8',
            '-log': 'warn',
            '-i': '',
            '-proc': '5'}
    while argv:
        if argv[0][0] == '-':
            opts[argv[0]] = argv[1]
            argv = argv[2:]
        else:
            argv = argv[1:]
    return opts


if __name__ == '__main__':
    config = getopts(argv)
    set_log_config(config['-log'])
    adresses = adresses_loading(filename=config['-f'])
    total_ping = 0.0
    unresponded = []
    proc_list = []

    if not '-h' in config:
        config['-h'] = input('Enter SSH host:\n')
    if not '-u' in config:
        config['-u'] = input('Enter SSH login:\n')
    if not '-p' in config:
        config['-p'] = input('Enter SSH password:\n')
    if not '-port' in config:
        config['-port'] = input('Enter port:\n')
    if not '-c' in config:
        config['-c'] = input('Enter number of tries:\n')

    logging.debug(config)
    logging.debug(adresses)


    def main(host):
        with SSHClientExt() as client:
            try:
                start_conn_time = time.clock()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                if config['-i'] != '':
                    client.connect(hostname=config['-h'], username=config['-u'], password=config['-p'],
                                   port=int(config['-port']), key_filename=config['-i'])
                else:
                    client.connect(hostname=config['-h'], username=config['-u'], password=config['-p'],
                                   port=int(config['-port']))
                logging.debug('Script execution time (SSH connect): {} sec'.format(time.clock() - start_conn_time))
                command = 'ping -c{} {}'.format(config['-c'], host)
                results = client.ping_exec(command)
                return results
            except Exception as err:
                logging.error(err, exc_info=exc_info)


    output = '\n' + '=' * 20 + " RESULTS: " + '=' * 20

    with concurrent.futures.ThreadPoolExecutor(max_workers=int(config['-proc'])) as executor:
        results = executor.map(main, adresses)
        for item in results:
            if item[0]:
                total_ping += item[1]
                output += '\nPing statistic for {}: {}'.format(item[2], item[0])
            else:
                unresponded.append(item[2])

    if total_ping > 0:
        output += '\n' + '=' * 50
        output += '\nAverage ping for {} hosts with {} tries: {}'.format((len(adresses) - len(unresponded)),
                                                                         config['-c'],
                                                                         total_ping / float(
                                                                             (len(adresses) - len(unresponded))))
        output += '\n' + '=' * 50
        if unresponded:
            output += '\nFor these hosts ping failed: {}'.format(', '.join(unresponded))
            output += '\n' + '=' * 50
        logging.warning(output)

# logging.warning('Average ping for {} hosts with {} tries: {}'.format((len(adresses) - len(unresponded)), config['-c'],total_ping / float((len(adresses) - len(unresponded)))))

logging.info('Script execution time: {} sec'.format(time.clock() - script_start_time))
