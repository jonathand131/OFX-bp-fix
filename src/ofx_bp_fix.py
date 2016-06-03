# coding=utf-8

"""
OFX BP Fix
Fix OFX files produced by the french bank Banque Populaire for proper import in Skrooge
"""

import os.path
import re
import sys

from ofxparse import ofxutil

from const_bp import BP_ATM, BP_CHECK, BP_COMM, BP_IXFER, BP_LOAN, BP_SEPA, BP_SUBSCRIPTION, \
    BP_XFER_LONG, BP_XFER_SHORT

from const_ofx import OFX_SRVCHG, OFX_XFER, OFX_DEP, OFX_REPEATPMT, OFX_CHECK, OFX_ATM, OFX_PAYMENT, OFX_DEBIT

# Prepare regexp
RE_TYPE_IN_NAME = re.compile(
    r'(?P<type>' + '|'.join((
        BP_SUBSCRIPTION,
        BP_XFER_SHORT,
        BP_XFER_LONG,
        BP_IXFER,
        BP_SEPA,
        BP_CHECK,
        BP_ATM,
        BP_COMM
    )) + r')($| (?P<name>.*))')
RE_CC_CL_TRANSACTION = re.compile(r'(?P<date>\d{6}) (?P<type>CB|SC):?\*\d{9}( (?P<name>.*))?')
RE_TRANSFER_MEMO = re.compile(r'(?P<id>\d{8})($| (?P<memo>.*))')
RE_CHECK_DEPOSIT = re.compile(r'DE \s*\d* CHEQUE\(S\)')


def fix_transaction_type_from_name(transac, stmttrnrs):
    """Fix transac type from name start"""
    match_type_in_name = RE_TYPE_IN_NAME.match(transac.name.data)
    if match_type_in_name:
        transac.trntype.data = {
            BP_SUBSCRIPTION: OFX_SRVCHG,
            BP_XFER_SHORT: OFX_XFER,
            BP_XFER_LONG: OFX_XFER,
            BP_IXFER: OFX_DEP,
            BP_SEPA: OFX_REPEATPMT,
            BP_CHECK: OFX_CHECK,
            BP_ATM: OFX_ATM,
            BP_COMM: OFX_SRVCHG,
        }.get(match_type_in_name.group('type'), transac.trntype.data)
        if match_type_in_name.group('name'):
            transac.name.data = match_type_in_name.group('name')
        if match_type_in_name.group('type') == BP_COMM:
            fix_commission(transac, stmttrnrs)


def fix_commission(transac, stmttrnrs):
    """Fix COMMISSION"""
    match_cb_sc_transaction = RE_CC_CL_TRANSACTION.match(transac.memo.data)
    if match_cb_sc_transaction:
        transac.name.data = match_cb_sc_transaction.group('name')
        transac.memo.data = match_cb_sc_transaction.group('date')
        checknum = transac.checknum.data
        for other_transac in stmttrnrs.stmtrs.banktranlist.stmttrn:
            if other_transac.checknum.data != checknum:
                continue
            if other_transac.name.data.startswith(match_cb_sc_transaction.group('name')):
                other_transac.name.data = match_cb_sc_transaction.group('name')
            if other_transac.memo.data.startswith(match_cb_sc_transaction.group('name')):
                other_transac.memo.data = match_cb_sc_transaction.group('name')


def fix_cc_cl_transaction(transac):
    """Fix credit card/contact less transactions"""
    match_cb_sc_transaction = RE_CC_CL_TRANSACTION.match(transac.name.data)
    if match_cb_sc_transaction:
        transac.trntype.data = OFX_PAYMENT
        transac.name.data = transac.memo.data
        transac.memo.data = "%s %s" % (match_cb_sc_transaction.group('type'), match_cb_sc_transaction.group('date'))


def fix_transfer(transac):
    """Fix transfer"""
    if transac.trntype.data == OFX_DEBIT:
        match_transfer_memo = RE_TRANSFER_MEMO.match(transac.memo.data)
        if match_transfer_memo:
            transac.trntype.data = OFX_XFER
            if match_transfer_memo.group('memo'):
                transac.memo.data = "%s (%s)" % (match_transfer_memo.group('memo'),
                                                 match_transfer_memo.group('id'))
    if transac.trntype.data == OFX_XFER:
        transac.checknum.data = ''


def fix_atm(transac):
    """""# Fix ATM"""
    if transac.trntype.data == OFX_ATM:
        transac.memo.data = "%s %s" % (transac.name.data, transac.memo.data)
        transac.name.data = BP_ATM


def fix_loan(transac):
    """Fix loan"""
    if transac.name.data == BP_LOAN:
        transac.name.data = "%s %s" % (transac.name.data, transac.checknum.data)
        transac.checknum.data = ''


def fix_check_deposit(transac):
    """""# Fix check deposit"""
    match_depot_cheque = RE_CHECK_DEPOSIT.match(transac.name.data)
    if match_depot_cheque:
        transac.trntype.data = OFX_CHECK
        transac.memo = transac.name
        transac.name.data = BP_CHECK


def fix_ofx(in_ofx, out_ofx):
    """
    Produce a new, corrected OFX file from the given original OFX file
    @param str in_ofx: OFX file to fix
    @param str out_ofx: path to write corrected OFX file
    """
    ofx = ofxutil.OfxUtil(in_ofx)

    for stmttrnrs in ofx.bankmsgsrsv1.stmttrnrs:
        for transaction in stmttrnrs.stmtrs.banktranlist.stmttrn:
            fix_transaction_type_from_name(transaction, stmttrnrs)
            fix_cc_cl_transaction(transaction)
            fix_transfer(transaction)
            fix_atm(transaction)
            fix_loan(transaction)
            fix_check_deposit(transaction)

    ofx.write(out_ofx)


def main():
    """
    Program main function
    """
    if len(sys.argv) < 2:
        sys.exit('Bad argument count')

    input_ofx = sys.argv[1]
    if len(sys.argv) > 2:
        output_ofx = sys.argv[2]
    else:
        output_ofx = "%s_corrected%s" % os.path.splitext(input_ofx)
    fix_ofx(input_ofx, output_ofx)


if __name__ == '__main__':
    main()
