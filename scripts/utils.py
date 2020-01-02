import argparse
import functools
import os
import time
from logging import DEBUG, FileHandler, Formatter, StreamHandler

import requests
import torch


def logInit(logger, log_dir, log_filename):
    '''
    Init the logger.
    '''
    log_fmt = Formatter('%(asctime)s %(name)s \
            %(lineno)d [%(levelname)s] [%(funcName)s] %(message)s ')
    handler = StreamHandler()
    handler.setLevel('INFO')
    handler.setFormatter(log_fmt)
    logger.addHandler(handler)

    handler = FileHandler(log_dir + log_filename, 'a')
    handler.setLevel(DEBUG)
    handler.setFormatter(log_fmt)
    logger.setLevel(DEBUG)
    logger.addHandler(handler)
    return logger


def sel_log(message, logger, debug=False):
    '''
    Use logger if specified one, and use print otherwise.
    Also it's possible to specify to use debug mode (default: info mode).
    The func name is the shorter version of selective_logging.
    '''
    if logger:
        if debug:
            logger.debug(message)
        else:
            logger.info(message)
    else:
        print(message)


def dec_timer(func):
    '''
    Decorator which measures the processing time of the func.
    '''
    # wraps func enable to hold the func name
    @functools.wraps(func)
    def _timer(*args, **kwargs):
        t0 = time.time()
        start_str = f'[{func.__name__}] start'
        if 'logger' in kwargs:
            logger = kwargs['logger']
        else:
            logger = None
        sel_log(start_str, logger)

        # run the func
        res = func(*args, **kwargs)

        end_str = f'[{func.__name__}] done in {time.time() - t0:.1f} s'
        sel_log(end_str, logger)
        return res

    return _timer


def send_line_notification(message):
    line_token = 'wCRJeXTW1HB54fPnopnBtqAz64OFH5ZqahPdbvseksG'
    endpoint = 'https://notify-api.line.me/api/notify'
    message = "\n{}".format(message)
    payload = {'message': message}
    headers = {'Authorization': 'Bearer {}'.format(line_token)}
    requests.post(endpoint, data=payload, headers=headers)


def parse_args(logger=None):
    '''
    Policy
    ------------
    * experiment id must be required
    '''
    parser = argparse.ArgumentParser(
        prog='XXX.py',
        usage='ex) python -e e001 -d -m "e001, basic experiment"',
        description='short explanation of args',
        add_help=True,
    )
    parser.add_argument('-t', '--checkpoint',
                        help='the checkpoint u use',
                        type=str,
                        required=False,
                        default=None)
    parser.add_argument('-d', '--debug',
                        help='whether or not to use debug mode',
                        action='store_true',
                        default=False)

    args = parser.parse_args()
    sel_log(f'args: {sorted(vars(args).items())}', logger)
    return args


def save_checkpoint(save_dir, exp_id, model, optimizer, scheduler,
                    histories, val_y_preds, val_y_trues, val_qa_ids,
                    current_fold, current_epoch, val_loss, val_metric):
    if not os.path.exists(f'{save_dir}/{exp_id}'):
        os.makedirs(f'../mnt/checkpoints/{exp_id}')
    # pth means pytorch
    cp_filename = f'{save_dir}/{exp_id}/' \
                  f'fold_{current_fold}_epoch_{current_epoch}' \
                  f'_{val_loss:.5f}_{val_metric:.5f}_checkpoint.pth'
    cp_dict = {
        'current_fold': current_fold,
        'current_epoch': current_epoch,
        'model_state_dict': model.state_dict(),
        'optim_state_dict': optimizer.state_dict(),
        'scheduler_state_dict': scheduler.state_dict(),
        'histories': histories,
    }
    sel_log(f'now saving checkpoint to {cp_filename} ...')
    torch.save(cp_dict, cp_filename)