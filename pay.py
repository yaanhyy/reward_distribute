# Useful Python 2.x script for Tezos bakers to calculate payouts for their delegators
# This is a highly edited payout calculation script which aims to be a bit friendlier while giving more information.
# Original credit goes to /u/8x1_ from https://reddit.com/r/tezos/comments/98jwb4/paypy_there_is_no_more_excuse_for_not_paying/
# Released under the MIT License - See bottom of file for license information

import urllib
import json
import random
import sys

####################################################################
# Edit the values below to customize the script for your own needs #
####################################################################

baker_address = 'tz1LFzD7HtsHJuvX8VCMBvofDeC4AZsU7UyP' # the address of the baker
baker_alias = 'bob' # alias of the baker wallet
hot_wallet_address = '' # if payouts are made from a non-baker address, enter it here (could be either tz1 or KT1)
wallet_alias = '' # alias of the hot wallet
default_fee_percent = 10 # default delegation service fee
special_addresses = [''] #['KT1...', 'KT1...'] special accounts that get a different fee, set to '' if none
special_fee_percent = 0 # delegation service fee for special accounts
tx_fee = 0.000001 # transaction fee on payouts
precision = 6 # Tezos supports up to 6 decimal places of precision

#######################################################
# You shouldn't need to edit anything below this line #
#######################################################

# get a random number to randomize which TzScan API mirror we use
api_mirror = random.randint(1,5)

# TzScan API URLs
api_url_head = 'https://api{}.tzscan.io/v2/head'.format(api_mirror) # info about current status
api_url_rewards = 'http://api{}.tzscan.io/v2/rewards_split/'.format(api_mirror) # info about rewards at specific cycle

# get current cycle info
response = urllib.urlopen(api_url_head)
data = json.loads(response.read())
level = int(data['level'])
cycle = (level - 1) // 4096
cycle_progress = round((float(level - 1) / 4096 - cycle) * 100, 2)

# display some info about status of current cycle and ETA until next cycle begins
print('Currently {}% through cycle {}.'.format(cycle_progress, cycle))
next_cycle = cycle + 1
# calculate how many minutes, hours, days until next cycle begins
eta_minutes = 4096 * next_cycle - level + 1
eta_hours = eta_minutes / 60
eta_days = eta_hours / 24
# make sure hours and minutes aren't greater than next larger unit of time
eta_hours = eta_hours % 24
eta_minutes = eta_minutes % 60
# prepare to print the ETA until the next cycle in a nice way
status_text = 'ETA until cycle {} begins is '.format(next_cycle)
if eta_days > 0:
    status_text += '{} day'.format(eta_days)
    if eta_days > 1:
        status_text += 's'
    status_text += ' '
if eta_hours > 0:
    status_text += '{} hour'.format(eta_hours)
    if eta_hours > 1:
        status_text += 's'
    status_text += ' '
if eta_minutes > 0:
    status_text += '{} minute'.format(eta_minutes)
    if eta_minutes > 1:
        status_text += 's'
# actually print the ETA info
print('{}.'.format(status_text))
print('')

# determine which cycle to use to calculate payouts
if len(sys.argv) != 2:
    cycle -= 6
    print ('No cycle passed in. Using most-recently unlocked rewards (cycle N-6) from cycle {}.'.format(cycle))
else:
    # a few sanity checks for the passed-in value
    is_valid = True
    error_txt = ''
    # make sure the value passed in is an integer
    if sys.argv[1].isdigit():
        # parameter is an int, now make sure we can use it
        tmp_cycle = int(sys.argv[1])
        if tmp_cycle > cycle: # cycle is in the future
            is_valid = False
            error_txt = 'ERROR: Cycle {} hasn\'t happened yet! We\'re still on cycle {}!\n'.format(tmp_cycle, cycle)
            error_txt += 'What do you think I am? Some kind of time traveler?'
        elif tmp_cycle == cycle: # cycle is in progress
            error_txt = 'WARNING: Cycle {} hasn\'t finished yet, so this data may not reflect final results.'.format(cycle)
    else:
        # value is not an int (or is negative, which looks like a string to the parser)
        is_valid = False
        error_txt = 'ERROR: The value passed in ({}) is not an integer, or is negative!'.format(sys.argv[1])

    # print the error message if necessary
    if error_txt != '':
        print('')
        print ('===================================================================================')
        print (error_txt)
        print ('===================================================================================')
        print ('')
        # quit if the value is invalid
        if is_valid == False:
            sys.exit()

    cycle = tmp_cycle
    print ('Calculating earnings and payouts for cycle {}.'.format(cycle))

# get rewards data
page = 0
response = urllib.urlopen('{}{}?cycle={}&number=50&p={}'.format(api_url_rewards, baker_address, cycle, page))
data = json.loads(response.read())

print ('')

total_delegators = int(data['delegators_nb'])
if total_delegators == 0:
    print ('No non-baker delegators for cycle {}.'.format(cycle))

pages = total_delegators / 50

paid_delegators = 0

total_staking_balance = long(data['delegate_staking_balance'])
baker_balance = total_staking_balance
total_rewards = long(data['blocks_rewards']) + \
                long(data['endorsements_rewards']) + \
                long(data['fees']) + \
                long(data['future_blocks_rewards']) + \
                long(data['future_endorsements_rewards']) + \
                long(data['gain_from_denounciation']) - \
                long(data['lost_deposit_from_denounciation']) - \
                long(data['lost_fees_denounciation']) - \
                long(data['lost_rewards_denounciation'])

# make sure there's actually something to pay out
if total_rewards <= 0:
    print ('WARNING: Total rewards this cycle is {}, so there\'s nothing to pay out. :('.format(total_rewards))
    sys.exit()

total_payouts_gross = 0
total_payouts = 0
total_fees = 0
net_earnings = total_rewards

# start a loop to load all pages of results
while True:
    # calculate and print out payment commands
    for del_balance in data['delegators_balance']:
        delegator_address = del_balance[0]['tz']
        bal = int(del_balance[1])

        # TzScan orders addresses by amount staked, so skip all the rest if we encounter a 0 balance
        if bal == 0:
            page = pages
            break

        baker_balance -= bal
        fee_percent = default_fee_percent

		# handle any special addresses
        for address in special_addresses:
            if delegator_address == address:
                fee_percent = special_fee_percent
                break

        # don't include your hot wallet when calculating payouts (in case your hot wallet is a KT1 address delegated to yourself)
        if delegator_address == hot_wallet_address:
            continue

        # calculate gross payout amount
        payout_gross = (float(bal) / total_staking_balance) * total_rewards
        total_payouts_gross += payout_gross
        # subtract fee
        payout = (payout_gross * (100 - fee_percent)) / 100
        total_fees += payout_gross - payout
        net_earnings -= payout
        # convert from mutes (0.000001 XTZ) to XTZ
        payout = round(payout / 1000000, precision)
        # display the payout command to pay this delegator, filtering out any zero-balance payouts
        if payout >= 0.000001:
            total_payouts += payout
            paid_delegators += 1
            payout_string = '{0:.6f}'.format(payout) # force tiny values to show all digits
            if wallet_alias:
                payout_alias = wallet_alias
            else:
                payout_alias = baker_alias
            print ('./tezos-client transfer {} from {} to {} --fee {}'.format(payout_string, payout_alias, delegator_address, tx_fee))

    # load the next page of results if necessary
    if page < pages:
        page += 1
        response = urllib.urlopen('{}{}?cycle={}&number=50&p={}'.format(api_url_rewards, baker_address, cycle, page))
        data = json.loads(response.read())
    else:
        break

# print some information about all payouts made for this cyle
if total_payouts > 0:
    result_txt = '\nTotal payouts made: {} to {} delegator'.format(total_payouts, paid_delegators)
    if paid_delegators > 1:
        result_txt +='s\n' # pluralize it!
    print (result_txt)

    # display the command to transfer total payout amount to the hot wallet
    if hot_wallet_address:
        print ('./tezos-client transfer {} from {} to {} --fee {}'.format(total_payouts, baker_alias, hot_wallet_address, tx_fee))

# convert the amounts to a human readable format
total_rewards = round(total_rewards / 1000000, precision)
net_earnings = round(net_earnings / 1000000, precision)
share_of_gross = round(net_earnings / total_rewards * 100, 2)
total_fees = round(total_fees / 1000000, precision)
total_staking_balance = round(float(total_staking_balance) / 1000000, precision)
baker_balance = round(float(baker_balance) / 1000000, precision)
baker_percentage = round(baker_balance / total_staking_balance * 100, 2)

# print out stats for this cycle's payouts
print ('')
print ('===============================================')
print ('Stats for cycle {}'.format(cycle))
print ('Total staked balance: {}'.format(total_staking_balance))
print ('Baker staked balance: {} ({}% of total)'.format(baker_balance, baker_percentage))
print ('Total (gross) earnings for cycle: {}'.format(total_rewards))
if total_payouts > 0:
    print ('Total (net) baker earnings: {} ({}% of gross) (that is, {} + {} as fees charged)'.format(net_earnings, share_of_gross, net_earnings - total_fees, total_fees))


