# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division
import io
import os
import shutil
import itertools
import gzip
import warnings
import tempfile
import atexit


import zarr
import h5py
import numpy as np
from numpy.testing import assert_array_equal, assert_array_almost_equal
from nose.tools import (assert_almost_equal, eq_, assert_in, assert_list_equal,
                        assert_raises)
from allel.io.vcf_read import (iter_vcf_chunks, read_vcf, vcf_to_zarr, vcf_to_hdf5,
                               vcf_to_npz, ANNTransformer, vcf_to_dataframe, vcf_to_csv,
                               vcf_to_recarray, read_vcf_headers)
from allel.compat import PY2
from allel.test.tools import compare_arrays


# needed for PY2/PY3 consistent behaviour
warnings.resetwarnings()
warnings.simplefilter('always')


# setup temp dir for testing
tempdir = tempfile.mkdtemp()
atexit.register(shutil.rmtree, tempdir)


def test_read_vcf_chunks():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')

    fields, samples, headers, it = iter_vcf_chunks(vcf_path, fields='*', chunk_length=4,
                                                   buffer_size=100)

    # check headers
    assert_in('q10', headers.filters)
    assert_in('s50', headers.filters)
    assert_in('AA', headers.infos)
    assert_in('AC', headers.infos)
    assert_in('AF', headers.infos)
    assert_in('AN', headers.infos)
    assert_in('DB', headers.infos)
    assert_in('DP', headers.infos)
    assert_in('H2', headers.infos)
    assert_in('NS', headers.infos)
    assert_in('DP', headers.formats)
    assert_in('GQ', headers.formats)
    assert_in('GT', headers.formats)
    assert_in('HQ', headers.formats)
    eq_(['NA00001', 'NA00002', 'NA00003'], headers.samples)
    assert_list_equal(['NA00001', 'NA00002', 'NA00003'], samples.tolist())
    eq_('1', headers.infos['AA']['Number'])
    eq_('String', headers.infos['AA']['Type'])
    eq_('Ancestral Allele', headers.infos['AA']['Description'])
    eq_('2', headers.formats['HQ']['Number'])
    eq_('Integer', headers.formats['HQ']['Type'])
    eq_('Haplotype Quality', headers.formats['HQ']['Description'])

    # check chunk lengths
    chunks = [chunk for chunk, _, _, _ in it]
    eq_(3, len(chunks))
    eq_(4, chunks[0]['variants/POS'].shape[0])
    eq_(4, chunks[1]['variants/POS'].shape[0])
    eq_(1, chunks[2]['variants/POS'].shape[0])

    # check chunk contents
    expected_fields = [
        # fixed fields
        'variants/CHROM',
        'variants/POS',
        'variants/ID',
        'variants/REF',
        'variants/ALT',
        'variants/QUAL',
        'variants/FILTER_PASS',
        'variants/FILTER_q10',
        'variants/FILTER_s50',
        # INFO fields
        'variants/AA',
        'variants/AC',
        'variants/AF',
        'variants/AN',
        'variants/DB',
        'variants/DP',
        'variants/H2',
        'variants/NS',
        # special computed fields
        'variants/altlen',
        'variants/numalt',
        'variants/is_snp',
        # FORMAT fields
        'calldata/GT',
        'calldata/GQ',
        'calldata/HQ',
        'calldata/DP',
    ]
    for chunk in chunks:
        assert_list_equal(sorted(expected_fields), sorted(chunk.keys()))


def test_fields_all():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    callset = read_vcf(vcf_path, fields='*')
    expected_fields = [
        'samples',
        # fixed fields
        'variants/CHROM',
        'variants/POS',
        'variants/ID',
        'variants/REF',
        'variants/ALT',
        'variants/QUAL',
        'variants/FILTER_PASS',
        'variants/FILTER_q10',
        'variants/FILTER_s50',
        # INFO fields
        'variants/AA',
        'variants/AC',
        'variants/AF',
        'variants/AN',
        'variants/DB',
        'variants/DP',
        'variants/H2',
        'variants/NS',
        # special computed fields
        'variants/altlen',
        'variants/numalt',
        'variants/is_snp',
        # FORMAT fields
        'calldata/GT',
        'calldata/GQ',
        'calldata/HQ',
        'calldata/DP',
    ]
    assert_list_equal(sorted(expected_fields), sorted(callset.keys()))


def test_fields_exclude():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    exclude = ['variants/altlen', 'ID', 'calldata/DP']
    callset = read_vcf(vcf_path, fields='*', exclude_fields=exclude)
    expected_fields = [
        'samples',
        # fixed fields
        'variants/CHROM',
        'variants/POS',
        'variants/REF',
        'variants/ALT',
        'variants/QUAL',
        'variants/FILTER_PASS',
        'variants/FILTER_q10',
        'variants/FILTER_s50',
        # INFO fields
        'variants/AA',
        'variants/AC',
        'variants/AF',
        'variants/AN',
        'variants/DB',
        'variants/DP',
        'variants/H2',
        'variants/NS',
        # special computed fields
        'variants/numalt',
        'variants/is_snp',
        # FORMAT fields
        'calldata/GT',
        'calldata/GQ',
        'calldata/HQ',
    ]
    assert_list_equal(sorted(expected_fields), sorted(callset.keys()))


def test_fields_rename():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    rename = {'CHROM': 'variants/chromosome',
              'variants/altlen': 'spam/eggs',
              'calldata/GT': 'foo/bar'}
    callset = read_vcf(vcf_path, fields='*', rename_fields=rename)
    print(sorted(callset.keys()))
    expected_fields = [
        'samples',
        # fixed fields
        'variants/chromosome',
        'variants/POS',
        'variants/ID',
        'variants/REF',
        'variants/ALT',
        'variants/QUAL',
        'variants/FILTER_PASS',
        'variants/FILTER_q10',
        'variants/FILTER_s50',
        # INFO fields
        'variants/AA',
        'variants/AC',
        'variants/AF',
        'variants/AN',
        'variants/DB',
        'variants/DP',
        'variants/H2',
        'variants/NS',
        # special computed fields
        'spam/eggs',
        'variants/numalt',
        'variants/is_snp',
        # FORMAT fields
        'foo/bar',
        'calldata/DP',
        'calldata/GQ',
        'calldata/HQ',
    ]
    assert_list_equal(sorted(expected_fields), sorted(callset.keys()))


def test_fields_default():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    callset = read_vcf(vcf_path)
    expected_fields = [
        'samples',
        'variants/CHROM',
        'variants/POS',
        'variants/ID',
        'variants/REF',
        'variants/ALT',
        'variants/QUAL',
        'variants/FILTER_PASS',
        'calldata/GT',
    ]
    assert_list_equal(sorted(expected_fields), sorted(callset.keys()))


def test_fields_all_variants():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    callset = read_vcf(vcf_path, fields='variants/*')
    expected_fields = [
        # fixed fields
        'variants/CHROM',
        'variants/POS',
        'variants/ID',
        'variants/REF',
        'variants/ALT',
        'variants/QUAL',
        'variants/FILTER_PASS',
        'variants/FILTER_q10',
        'variants/FILTER_s50',
        # INFO fields
        'variants/AA',
        'variants/AC',
        'variants/AF',
        'variants/AN',
        'variants/DB',
        'variants/DP',
        'variants/H2',
        'variants/NS',
        # special computed fields
        'variants/altlen',
        'variants/numalt',
        'variants/is_snp',
    ]
    assert_list_equal(sorted(expected_fields), sorted(callset.keys()))


def test_fields_info():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    callset = read_vcf(vcf_path, fields='INFO')
    expected_fields = [
        # INFO fields
        'variants/AA',
        'variants/AC',
        'variants/AF',
        'variants/AN',
        'variants/DB',
        'variants/DP',
        'variants/H2',
        'variants/NS',
    ]
    assert_list_equal(sorted(expected_fields), sorted(callset.keys()))


def test_fields_filter():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    callset1 = read_vcf(vcf_path, fields='FILTER')
    expected_fields = [
        'variants/FILTER_PASS',
        'variants/FILTER_q10',
        'variants/FILTER_s50',
    ]
    assert_list_equal(sorted(expected_fields), sorted(callset1.keys()))

    # this has explicit PASS definition in header, shouldn't cause problems
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'test16.vcf')
    callset2 = read_vcf(vcf_path, fields='FILTER')
    expected_fields = [
        'variants/FILTER_PASS',
        'variants/FILTER_q10',
        'variants/FILTER_s50',
    ]
    assert_list_equal(sorted(expected_fields), sorted(callset2.keys()))
    for k in callset1.keys():
        assert_array_equal(callset1[k], callset2[k])


def test_fields_all_calldata():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    callset = read_vcf(vcf_path, fields='calldata/*')
    expected_fields = [
        'calldata/GT',
        'calldata/GQ',
        'calldata/HQ',
        'calldata/DP',
    ]
    assert_list_equal(sorted(expected_fields), sorted(callset.keys()))


def test_fields_selected():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')

    # without samples
    callset = read_vcf(vcf_path,
                       fields=['CHROM', 'variants/POS', 'AC', 'variants/AF', 'GT',
                               'calldata/HQ', 'FILTER_q10', 'variants/numalt'])
    expected_fields = [
        'variants/CHROM',
        'variants/POS',
        'variants/FILTER_q10',
        'variants/AC',
        'variants/AF',
        'variants/numalt',
        # FORMAT fields
        'calldata/GT',
        'calldata/HQ',
    ]
    assert_list_equal(sorted(expected_fields), sorted(callset.keys()))

    # with samples
    callset = read_vcf(vcf_path,
                       fields=['CHROM', 'variants/POS', 'AC', 'variants/AF', 'GT',
                               'calldata/HQ', 'FILTER_q10', 'variants/numalt', 'samples'],
                       chunk_length=4, buffer_size=100)
    expected_fields = [
        'samples',
        'variants/CHROM',
        'variants/POS',
        'variants/FILTER_q10',
        'variants/AC',
        'variants/AF',
        'variants/numalt',
        # FORMAT fields
        'calldata/GT',
        'calldata/HQ',
    ]
    assert_list_equal(sorted(expected_fields), sorted(callset.keys()))


def test_fields_dups():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')

    # silently collapse dups
    callset = read_vcf(vcf_path,
                       fields=['CHROM', 'variants/CHROM', 'variants/AF', 'variants/AF',
                               'numalt', 'variants/numalt'])
    expected_fields = [
        'variants/CHROM',
        'variants/AF',
        'variants/numalt'
    ]
    assert_list_equal(sorted(expected_fields), sorted(callset.keys()))


def test_fields_dups_case_insensitive():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'altlen.vcf')

    # allow case-insensitive dups here (but not in vcf_to_zarr)
    callset = read_vcf(vcf_path, fields=['ALTLEN', 'altlen'])
    expected_fields = [
        'variants/ALTLEN',
        'variants/altlen',
    ]
    assert_list_equal(sorted(expected_fields), sorted(callset.keys()))


def _test_read_vcf_content(vcf, chunk_length, buffer_size):

    # object dtype for strings

    if isinstance(vcf, str):
        input_file = vcf
        close = False
    else:
        input_file = vcf()
        close = True

    callset = read_vcf(input_file,
                       fields='*',
                       chunk_length=chunk_length,
                       buffer_size=buffer_size,
                       types={'calldata/DP': 'object'})
    if close:
        input_file.close()

    # samples
    eq_((3,), callset['samples'].shape)
    eq_('O', callset['samples'].dtype.kind)
    assert_list_equal(['NA00001', 'NA00002', 'NA00003'], callset['samples'].tolist())

    # fixed fields
    eq_((9,), callset['variants/CHROM'].shape)
    eq_(np.dtype(object), callset['variants/CHROM'].dtype)
    eq_('19', callset['variants/CHROM'][0])
    eq_((9,), callset['variants/POS'].shape)
    eq_(111, callset['variants/POS'][0])
    eq_((9,), callset['variants/ID'].shape)
    eq_(np.dtype(object), callset['variants/ID'].dtype)
    eq_('rs6054257', callset['variants/ID'][2])
    eq_((9,), callset['variants/REF'].shape)
    eq_(np.dtype(object), callset['variants/REF'].dtype)
    eq_('A', callset['variants/REF'][0])
    eq_((9, 3), callset['variants/ALT'].shape)
    eq_(np.dtype(object), callset['variants/ALT'].dtype)
    eq_('ATG', callset['variants/ALT'][8, 1])
    eq_((9,), callset['variants/QUAL'].shape)
    eq_(10.0, callset['variants/QUAL'][1])
    eq_((9,), callset['variants/FILTER_PASS'].shape)
    eq_(True, callset['variants/FILTER_PASS'][2])
    eq_(False, callset['variants/FILTER_PASS'][3])
    eq_((9,), callset['variants/FILTER_q10'].shape)
    eq_(True, callset['variants/FILTER_q10'][3])

    # INFO fields
    eq_(3, callset['variants/NS'][2])
    eq_(.5, callset['variants/AF'][2, 0])
    eq_(True, callset['variants/DB'][2])
    eq_((3, 1, -1), tuple(callset['variants/AC'][6]))

    # test calldata content
    eq_((9, 3, 2), callset['calldata/GT'].shape)
    eq_((0, 0), tuple(callset['calldata/GT'][0, 0]))
    eq_((-1, -1), tuple(callset['calldata/GT'][6, 2]))
    eq_((-1, -1), tuple(callset['calldata/GT'][7, 2]))
    eq_((9, 3, 2), callset['calldata/HQ'].shape)
    eq_((10, 15), tuple(callset['calldata/HQ'][0, 0]))
    eq_((9, 3), callset['calldata/DP'].shape)
    eq_(np.dtype(object), callset['calldata/DP'].dtype)
    eq_(('4', '2', '3'), tuple(callset['calldata/DP'][6]))

    # String (S) dtype

    if isinstance(vcf, str):
        input_file = vcf
        close = False
    else:
        input_file = vcf()
        close = True

    types = {'CHROM': 'S12', 'ID': 'S20', 'REF': 'S20', 'ALT': 'S20', 'calldata/DP': 'S3',
             'samples': 'S20'}
    callset = read_vcf(input_file, fields='*', chunk_length=chunk_length,
                       buffer_size=buffer_size, types=types)
    if close:
        input_file.close()

    # samples
    eq_((3,), callset['samples'].shape)
    eq_('S', callset['samples'].dtype.kind)
    assert_list_equal([b'NA00001', b'NA00002', b'NA00003'], callset['samples'].tolist())

    # fixed fields
    eq_((9,), callset['variants/CHROM'].shape)
    eq_('S', callset['variants/CHROM'].dtype.kind)
    eq_(b'19', callset['variants/CHROM'][0])
    eq_((9,), callset['variants/POS'].shape)
    eq_(111, callset['variants/POS'][0])
    eq_((9,), callset['variants/ID'].shape)
    eq_('S', callset['variants/ID'].dtype.kind)
    eq_(b'rs6054257', callset['variants/ID'][2])
    eq_((9,), callset['variants/REF'].shape)
    eq_(b'A', callset['variants/REF'][0])
    eq_('S', callset['variants/REF'].dtype.kind)
    eq_((9, 3), callset['variants/ALT'].shape)
    eq_(b'ATG', callset['variants/ALT'][8, 1])
    eq_('S', callset['variants/ALT'].dtype.kind)
    eq_((9,), callset['variants/QUAL'].shape)
    eq_(10.0, callset['variants/QUAL'][1])
    eq_((9,), callset['variants/FILTER_PASS'].shape)
    eq_(True, callset['variants/FILTER_PASS'][2])
    eq_(False, callset['variants/FILTER_PASS'][3])
    eq_((9,), callset['variants/FILTER_q10'].shape)
    eq_(True, callset['variants/FILTER_q10'][3])

    # INFO fields
    eq_(3, callset['variants/NS'][2])
    eq_(.5, callset['variants/AF'][2, 0])
    eq_(True, callset['variants/DB'][2])
    eq_((3, 1, -1), tuple(callset['variants/AC'][6]))

    # test calldata content
    eq_((9, 3, 2), callset['calldata/GT'].shape)
    eq_((0, 0), tuple(callset['calldata/GT'][0, 0]))
    eq_((-1, -1), tuple(callset['calldata/GT'][6, 2]))
    eq_((-1, -1), tuple(callset['calldata/GT'][7, 2]))
    eq_((9, 3, 2), callset['calldata/HQ'].shape)
    eq_((10, 15), tuple(callset['calldata/HQ'][0, 0]))
    eq_((9, 3), callset['calldata/DP'].shape)
    eq_('S', callset['calldata/DP'].dtype.kind)
    eq_((b'4', b'2', b'3'), tuple(callset['calldata/DP'][6]))


def test_inputs():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')

    with open(vcf_path, mode='rb') as f:
        data = f.read(-1)

    inputs = (vcf_path,
              vcf_path + '.gz',
              lambda: open(vcf_path, mode='rb'),
              lambda: gzip.open(vcf_path + '.gz', mode='rb'),
              lambda: io.BytesIO(data),
              lambda: io.BytesIO(data.replace(b'\n', b'\r')),
              lambda: io.BytesIO(data.replace(b'\n', b'\r\n')))

    chunk_length = 3
    buffer_size = 10

    for i in inputs:
        _test_read_vcf_content(i, chunk_length, buffer_size)


def test_chunk_lengths():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    chunk_lengths = 1, 2, 3, 5, 10, 20
    buffer_size = 10

    for chunk_length in chunk_lengths:
        _test_read_vcf_content(vcf_path, chunk_length, buffer_size)


def test_buffer_sizes():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    chunk_length = 3
    buffer_sizes = 1, 2, 4, 8, 16, 32, 64, 128, 256, 512

    for buffer_size in buffer_sizes:
        _test_read_vcf_content(vcf_path, chunk_length, buffer_size)


def test_utf8():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.utf8.vcf')
    callset = read_vcf(vcf_path, fields='*')

    # samples
    eq_((3,), callset['samples'].shape)
    eq_('O', callset['samples'].dtype.kind)
    assert_list_equal([u'NA00001', u'Γεια σου κόσμε!', u'NA00003'],
                      callset['samples'].tolist())

    # CHROM
    eq_((9,), callset['variants/CHROM'].shape)
    eq_(np.dtype(object), callset['variants/CHROM'].dtype)
    eq_('19', callset['variants/CHROM'][0])
    eq_(u'Njatjeta Botë!', callset['variants/CHROM'][-2])

    # POS
    eq_((9,), callset['variants/POS'].shape)
    eq_(111, callset['variants/POS'][0])

    # ID
    eq_((9,), callset['variants/ID'].shape)
    eq_(np.dtype(object), callset['variants/ID'].dtype)
    eq_('foo', callset['variants/ID'][0])
    eq_(u'¡Hola mundo!', callset['variants/ID'][1])

    # REF
    eq_((9,), callset['variants/REF'].shape)
    eq_(np.dtype(object), callset['variants/REF'].dtype)
    eq_('A', callset['variants/REF'][0])

    # ALT
    eq_((9, 3), callset['variants/ALT'].shape)
    eq_(np.dtype(object), callset['variants/ALT'].dtype)
    eq_('ATG', callset['variants/ALT'][8, 1])

    # QUAL
    eq_((9,), callset['variants/QUAL'].shape)
    eq_(10.0, callset['variants/QUAL'][1])

    # FILTER
    eq_((9,), callset['variants/FILTER_PASS'].shape)
    eq_(True, callset['variants/FILTER_PASS'][2])
    eq_(False, callset['variants/FILTER_PASS'][5])
    eq_((9,), callset[u'variants/FILTER_Helló_világ!'].shape)
    eq_(False, callset[u'variants/FILTER_Helló_világ!'][0])
    eq_(True, callset[u'variants/FILTER_Helló_világ!'][5])

    # INFO fields
    eq_(u'foo', callset['variants/TEXT'][0])
    eq_(u'こんにちは世界', callset['variants/TEXT'][4])

    # calldata
    eq_((9, 3, 2), callset['calldata/GT'].shape)
    eq_((0, 0), tuple(callset['calldata/GT'][0, 0]))
    eq_((-1, -1), tuple(callset['calldata/GT'][6, 2]))
    eq_((-1, -1), tuple(callset['calldata/GT'][7, 2]))
    eq_((9, 3, 2), callset['calldata/HQ'].shape)
    eq_((10, 15), tuple(callset['calldata/HQ'][0, 0]))
    eq_((9, 3), callset['calldata/DP'].shape)
    eq_((4, 2, 3), tuple(callset['calldata/DP'][6]))
    eq_((u'foo', u'Hej Världen!', u'.'), tuple(callset['calldata/GTXT'][0]))


def test_truncation_chrom():

    input_data = (b"#CHROM\n"
                  b"2L\n"
                  b"2R\n")

    # with and without final line terminator
    for data in (input_data, input_data[:-1]):

        for string_type in 'S10', 'object':
            input_file = io.BytesIO(data)
            callset = read_vcf(input_file, fields=['CHROM', 'samples'],
                               types={'CHROM': string_type})

            # check fields
            expected_fields = ['variants/CHROM']
            assert_list_equal(sorted(expected_fields), sorted(callset.keys()))

            # check data content
            a = callset['variants/CHROM']
            eq_(2, len(a))
            if string_type == 'S10':
                eq_(b'2L', a[0])
                eq_(b'2R', a[1])
            else:
                eq_('2L', a[0])
                eq_('2R', a[1])


def test_truncation_pos():

    input_data = (b"#CHROM\tPOS\n"
                  b"2L\t12\n"
                  b"2R\t34\n")

    # with and without final line terminator
    for data in (input_data, input_data[:-1]):

        input_file = io.BytesIO(data)
        callset = read_vcf(input_file, fields=['POS', 'samples'])

        # check fields
        expected_fields = ['variants/POS']
        assert_list_equal(sorted(expected_fields), sorted(callset.keys()))

        # check data content
        a = callset['variants/POS']
        eq_(2, len(a))
        eq_(12, a[0])
        eq_(34, a[1])


def test_truncation_id():

    input_data = (b"#CHROM\tPOS\tID\n"
                  b"2L\t12\tfoo\n"
                  b"2R\t34\tbar\n")

    # with and without final line terminator
    for data in (input_data, input_data[:-1]):

        for string_type in 'S10', 'object':
            input_file = io.BytesIO(data)
            callset = read_vcf(input_file, fields=['ID', 'samples'],
                               types={'ID': string_type})

            # check fields
            expected_fields = ['variants/ID']
            assert_list_equal(sorted(expected_fields), sorted(callset.keys()))

            # check data content
            a = callset['variants/ID']
            eq_(2, len(a))
            if string_type == 'S10':
                eq_(b'foo', a[0])
                eq_(b'bar', a[1])
            else:
                eq_('foo', a[0])
                eq_('bar', a[1])


def test_truncation_ref():

    input_data = (b"#CHROM\tPOS\tID\tREF\n"
                  b"2L\t12\tfoo\tA\n"
                  b"2R\t34\tbar\tC\n")

    # with and without final line terminator
    for data in (input_data, input_data[:-1]):

        for string_type in 'S10', 'object':
            input_file = io.BytesIO(data)
            callset = read_vcf(input_file, fields=['REF', 'samples'],
                               types={'REF': string_type})

            # check fields
            expected_fields = ['variants/REF']
            assert_list_equal(sorted(expected_fields), sorted(callset.keys()))

            # check data content
            a = callset['variants/REF']
            eq_(2, len(a))
            if string_type == 'S10':
                eq_(b'A', a[0])
                eq_(b'C', a[1])
            else:
                eq_('A', a[0])
                eq_('C', a[1])


def test_truncation_alt():

    input_data = (b"#CHROM\tPOS\tID\tREF\tALT\n"
                  b"2L\t12\tfoo\tA\tC\n"
                  b"2R\t34\tbar\tC\tG\n")

    # with and without final line terminator
    for data in (input_data, input_data[:-1]):

        for string_type in 'S10', 'object':
            input_file = io.BytesIO(data)
            callset = read_vcf(input_file, fields=['ALT', 'samples'], numbers=dict(ALT=1),
                               types={'ALT': string_type})

            # check fields
            expected_fields = ['variants/ALT']
            assert_list_equal(sorted(expected_fields), sorted(callset.keys()))

            # check data content
            a = callset['variants/ALT']
            eq_(2, len(a))
            if string_type == 'S10':
                eq_(b'C', a[0])
                eq_(b'G', a[1])
            else:
                eq_('C', a[0])
                eq_('G', a[1])


def test_truncation_qual():

    input_data = (b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\n"
                  b"2L\t12\tfoo\tA\tC\t1.2\n"
                  b"2R\t34\tbar\tC\tG\t3.4\n")

    # with and without final line terminator
    for data in (input_data, input_data[:-1]):

        input_file = io.BytesIO(data)
        callset = read_vcf(input_file, fields=['QUAL', 'samples'])

        # check fields
        expected_fields = ['variants/QUAL']
        assert_list_equal(sorted(expected_fields), sorted(callset.keys()))

        # check data content
        a = callset['variants/QUAL']
        eq_(2, len(a))
        assert_almost_equal(1.2, a[0], places=6)
        assert_almost_equal(3.4, a[1], places=6)


def test_truncation_filter():

    input_data = (b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\n"
                  b"2L\t12\tfoo\tA\tC\t1.2\t.\n"
                  b"2R\t34\tbar\tC\tG\t3.4\tPASS\n"
                  b"2R\t56\tbaz\tG\tT\t56.77\tq10,s50\n")

    # with and without final line terminator
    for data in (input_data, input_data[:-1]):

        input_file = io.BytesIO(data)
        callset = read_vcf(input_file,
                           fields=['FILTER_PASS', 'FILTER_q10', 'FILTER_s50', 'samples'])

        # check fields
        expected_fields = ['variants/FILTER_PASS', 'variants/FILTER_q10',
                           'variants/FILTER_s50']
        assert_list_equal(sorted(expected_fields), sorted(callset.keys()))

        # check data content
        a = callset['variants/FILTER_PASS']
        eq_(3, len(a))
        assert_list_equal([False, True, False], a.tolist())
        a = callset['variants/FILTER_q10']
        eq_(3, len(a))
        assert_list_equal([False, False, True], a.tolist())
        a = callset['variants/FILTER_s50']
        eq_(3, len(a))
        assert_list_equal([False, False, True], a.tolist())


def test_truncation_info():

    input_data = (b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
                  b"2L\t12\tfoo\tA\tC\t1.2\t.\tfoo=42;bar=1.2\n"
                  b"2R\t34\tbar\tC\tG\t3.4\tPASS\t.\n"
                  b"2R\t56\tbaz\tG\tT\t56.77\tq10,s50\t\n")

    # with and without final line terminator
    for data in (input_data, input_data[:-1]):

        input_file = io.BytesIO(data)
        callset = read_vcf(input_file,
                           fields=['foo', 'bar', 'samples'],
                           types=dict(foo='Integer', bar='Float'))

        # check fields
        expected_fields = ['variants/foo', 'variants/bar']
        assert_list_equal(sorted(expected_fields), sorted(callset.keys()))

        # check data content
        a = callset['variants/foo']
        eq_(3, len(a))
        eq_(42, a[0])
        eq_(-1, a[1])
        eq_(-1, a[2])
        a = callset['variants/bar']
        eq_(3, len(a))
        assert_almost_equal(1.2, a[0], places=6)
        assert np.isnan(a[1])
        assert np.isnan(a[2])


def test_truncation_format():

    input_data = (b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\n"
                  b"2L\t12\tfoo\tA\tC\t1.2\t.\tfoo=42;bar=1.2\tGT:GQ\n"
                  b"2R\t34\tbar\tC\tG\t3.4\tPASS\t.\t.\n"
                  b"2R\t56\tbaz\tG\tT\t56.77\tq10,s50\t\t\n")

    # with and without final line terminator
    for data in (input_data, input_data[:-1]):

        input_file = io.BytesIO(data)
        callset = read_vcf(input_file,
                           fields=['foo', 'bar', 'samples'],
                           types=dict(foo='Integer', bar='Float'))

        # check fields
        expected_fields = ['variants/foo', 'variants/bar']
        assert_list_equal(sorted(expected_fields), sorted(callset.keys()))

        # check data content
        a = callset['variants/foo']
        eq_(3, len(a))
        eq_(42, a[0])
        eq_(-1, a[1])
        eq_(-1, a[2])
        a = callset['variants/bar']
        eq_(3, len(a))
        assert_almost_equal(1.2, a[0], places=6)
        assert np.isnan(a[1])
        assert np.isnan(a[2])


def test_truncation_calldata():

    input_data = (b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\n"
                  b"2L\t12\tfoo\tA\tC\t1.2\t.\tfoo=42;bar=1.2\tGT:GQ\t0/1:12\t1/2:34\n"
                  b"2R\t34\tbar\tC\tG\t3.4\tPASS\t.\tGT\t./.\n"
                  b"2R\t56\tbaz\tG\tT\t56.77\tq10,s50\t\n")

    # with and without final line terminator
    for data in (input_data, input_data[:-1]):

        input_file = io.BytesIO(data)
        callset = read_vcf(input_file,
                           fields=['calldata/GT', 'calldata/GQ', 'samples'],
                           types={'calldata/GT': 'i1', 'calldata/GQ': 'i2'})

        # check fields
        expected_fields = ['calldata/GT', 'calldata/GQ', 'samples']
        assert_list_equal(sorted(expected_fields), sorted(callset.keys()))

        # check data content
        eq_(2, len(callset['samples']))
        assert_list_equal(['S2', 'S1'], callset['samples'].tolist())
        a = callset['calldata/GT']
        eq_((3, 2, 2), a.shape)
        eq_((0, 1), tuple(a[0, 0]))
        eq_((1, 2), tuple(a[0, 1]))
        eq_((-1, -1), tuple(a[1, 0]))
        eq_((-1, -1), tuple(a[1, 1]))
        eq_((-1, -1), tuple(a[2, 0]))
        eq_((-1, -1), tuple(a[2, 1]))

        a = callset['calldata/GQ']
        eq_((3, 2), a.shape)
        eq_(12, a[0, 0])
        eq_(34, a[0, 1])
        eq_(-1, a[1, 0])
        eq_(-1, a[1, 1])
        eq_(-1, a[2, 0])
        eq_(-1, a[2, 1])


def test_info_types():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')

    for dtype in ('i1', 'i2', 'i4', 'i8', 'u1', 'u2', 'u4', 'u8', 'f4', 'f8', 'S10',
                  'object'):
        callset = read_vcf(vcf_path, fields=['variants/DP', 'variants/AC'],
                           types={'variants/DP': dtype, 'variants/AC': dtype},
                           numbers={'variants/AC': 3})
        eq_(np.dtype(dtype), callset['variants/DP'].dtype)
        eq_((9,), callset['variants/DP'].shape)
        eq_((9, 3), callset['variants/AC'].shape)


def test_vcf_types():

    input_data = (
        b'##INFO=<ID=foo,Number=1,Type=String,Description="Testing 123.">\n'
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\n"
        b"2L\t12\t.\tA\tC\t.\t.\tfoo=bar\t.\n"
    )
    callset = read_vcf(io.BytesIO(input_data), fields=['foo'])
    eq_(np.dtype(object), callset['variants/foo'].dtype)

    input_data = (
        b'##INFO=<ID=foo,Number=1,Type=Integer,Description="Testing 123.">\n'
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\n"
        b"2L\t12\t.\tA\tC\t.\t.\tfoo=42\t.\n"
    )
    callset = read_vcf(io.BytesIO(input_data), fields=['foo'])
    eq_(np.dtype('i4'), callset['variants/foo'].dtype)

    input_data = (
        b'##INFO=<ID=foo,Number=1,Type=Float,Description="Testing 123.">\n'
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\n"
        b"2L\t12\t.\tA\tC\t.\t.\tfoo=42.0\t.\n"
    )
    callset = read_vcf(io.BytesIO(input_data), fields=['foo'])
    eq_(np.dtype('f4'), callset['variants/foo'].dtype)

    input_data = (
        b'##INFO=<ID=foo,Number=1,Type=Character,Description="Testing 123.">\n'
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\n"
        b"2L\t12\t.\tA\tC\t.\t.\tfoo=b\t.\n"
    )
    callset = read_vcf(io.BytesIO(input_data), fields=['foo'])
    eq_(np.dtype('S1'), callset['variants/foo'].dtype)


def test_genotype_types():

    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    for dtype in 'i1', 'i2', 'i4', 'i8', 'u1', 'u2', 'u4', 'u8', 'S3', 'object':
        callset = read_vcf(vcf_path, fields=['GT'], types={'GT': dtype},
                           numbers={'GT': 2})
        eq_(np.dtype(dtype), callset['calldata/GT'].dtype)
        eq_((9, 3, 2), callset['calldata/GT'].shape)

    # non-GT field with genotype dtype

    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\tS2\tS3\n"
        b"2L\t12\t.\tA\t.\t.\t.\t.\tCustomGT:CustomGQ\t0/0/0:11\t0/1/2:12\t././.:.\n"
        b"2L\t34\t.\tC\tT\t.\t.\t.\tCustomGT:CustomGQ\t0/1/2:22\t3/3/.:33\t.\n"
        b"3R\t45\t.\tG\tA,T\t.\t.\t.\tCustomGT:CustomGQ\t0/1:.\t5:12\t\n"
    )
    callset = read_vcf(io.BytesIO(input_data),
                       fields=['calldata/CustomGT', 'calldata/CustomGQ'],
                       numbers={'calldata/CustomGT': 3, 'calldata/CustomGQ': 1},
                       types={'calldata/CustomGT': 'genotype/i1',
                              'calldata/CustomGQ': 'i2'})

    e = np.array([[[0, 0, 0], [0, 1, 2], [-1, -1, -1]],
                  [[0, 1, 2], [3, 3, -1], [-1, -1, -1]],
                  [[0, 1, -1], [5, -1, -1], [-1, -1, -1]]], dtype='i1')
    a = callset['calldata/CustomGT']
    assert_array_equal(e, a)
    eq_(e.dtype, a.dtype)

    e = np.array([[11, 12, -1],
                  [22, 33, -1],
                  [-1, 12, -1]], dtype='i2')
    a = callset['calldata/CustomGQ']
    assert_array_equal(e, a)
    eq_(e.dtype, a.dtype)


def test_calldata_types():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')

    for dtype in ('i1', 'i2', 'i4', 'i8', 'u1', 'u2', 'u4', 'u8', 'f4', 'f8', 'S10',
                  'object'):
        callset = read_vcf(vcf_path, fields=['HQ'], types={'HQ': dtype},
                           numbers={'HQ': 2})
        eq_(np.dtype(dtype), callset['calldata/HQ'].dtype)
        eq_((9, 3, 2), callset['calldata/HQ'].shape)


def test_genotype_ploidy():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')

    callset = read_vcf(vcf_path, fields='GT', numbers=dict(GT=1))
    gt = callset['calldata/GT']
    eq_((9, 3), gt.shape)
    eq_((0, 0, 0), tuple(gt[8, :]))

    callset = read_vcf(vcf_path, fields='GT', numbers=dict(GT=2))
    gt = callset['calldata/GT']
    eq_((9, 3, 2), gt.shape)
    eq_((0, -1), tuple(gt[8, 0]))
    eq_((0, 1), tuple(gt[8, 1]))
    eq_((0, 2), tuple(gt[8, 2]))

    callset = read_vcf(vcf_path, fields='GT', numbers=dict(GT=3))
    gt = callset['calldata/GT']
    eq_((9, 3, 3), gt.shape)
    eq_((0, -1, -1), tuple(gt[8, 0]))
    eq_((0, 1, -1), tuple(gt[8, 1]))
    eq_((0, 2, -1), tuple(gt[8, 2]))


def test_fills_info():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')

    callset = read_vcf(vcf_path, fields='AN', numbers=dict(AN=1))
    a = callset['variants/AN']
    eq_((9,), a.shape)
    eq_(-1, a[0])
    eq_(-1, a[1])
    eq_(-1, a[2])

    callset = read_vcf(vcf_path, fields='AN', numbers=dict(AN=1), fills=dict(AN=-2))
    a = callset['variants/AN']
    eq_((9,), a.shape)
    eq_(-2, a[0])
    eq_(-2, a[1])
    eq_(-2, a[2])

    callset = read_vcf(vcf_path, fields='AN', numbers=dict(AN=1), fills=dict(AN=-1))
    a = callset['variants/AN']
    eq_((9,), a.shape)
    eq_(-1, a[0])
    eq_(-1, a[1])
    eq_(-1, a[2])


def test_fills_genotype():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')

    callset = read_vcf(vcf_path, fields='GT', numbers=dict(GT=2))
    gt = callset['calldata/GT']
    eq_((9, 3, 2), gt.shape)
    eq_((0, -1), tuple(gt[8, 0]))
    eq_((0, 1), tuple(gt[8, 1]))
    eq_((0, 2), tuple(gt[8, 2]))

    callset = read_vcf(vcf_path, fields='GT', numbers=dict(GT=2), fills=dict(GT=-2))
    gt = callset['calldata/GT']
    eq_((9, 3, 2), gt.shape)
    eq_((0, -2), tuple(gt[8, 0]))
    eq_((0, 1), tuple(gt[8, 1]))
    eq_((0, 2), tuple(gt[8, 2]))

    callset = read_vcf(vcf_path, fields='GT', numbers=dict(GT=3), fills=dict(GT=-1))
    gt = callset['calldata/GT']
    eq_((9, 3, 3), gt.shape)
    eq_((0, -1, -1), tuple(gt[8, 0]))
    eq_((0, 1, -1), tuple(gt[8, 1]))
    eq_((0, 2, -1), tuple(gt[8, 2]))


def test_fills_calldata():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')

    callset = read_vcf(vcf_path, fields='HQ', numbers=dict(HQ=2))
    a = callset['calldata/HQ']
    eq_((9, 3, 2), a.shape)
    eq_((10, 15), tuple(a[0, 0]))
    eq_((-1, -1), tuple(a[7, 0]))
    eq_((-1, -1), tuple(a[8, 0]))

    callset = read_vcf(vcf_path, fields='HQ', numbers=dict(HQ=2), fills=dict(HQ=-2))
    a = callset['calldata/HQ']
    eq_((9, 3, 2), a.shape)
    eq_((10, 15), tuple(a[0, 0]))
    eq_((-2, -2), tuple(a[7, 0]))
    eq_((-2, -2), tuple(a[8, 0]))

    callset = read_vcf(vcf_path, fields='HQ', numbers=dict(HQ=2), fills=dict(HQ=-1))
    a = callset['calldata/HQ']
    eq_((9, 3, 2), a.shape)
    eq_((10, 15), tuple(a[0, 0]))
    eq_((-1, -1), tuple(a[7, 0]))
    eq_((-1, -1), tuple(a[8, 0]))


def test_numbers():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')

    callset = read_vcf(vcf_path, fields=['ALT'], numbers=dict(ALT=1))
    a = callset['variants/ALT']
    eq_((9,), a.shape)
    eq_('A', a[8])

    callset = read_vcf(vcf_path, fields=['ALT'], numbers=dict(ALT=2),
                       types=dict(ALT='S4'))
    a = callset['variants/ALT']
    eq_((9, 2), a.shape)
    eq_(b'A', a[8, 0])
    eq_(b'ATG', a[8, 1])

    callset = read_vcf(vcf_path, fields=['ALT'], numbers=dict(ALT=3),
                       types=dict(ALT='S4'))
    a = callset['variants/ALT']
    eq_((9, 3), a.shape)
    eq_(b'A', a[8, 0])
    eq_(b'ATG', a[8, 1])
    eq_(b'C', a[8, 2])

    callset = read_vcf(vcf_path, fields=['AC'], numbers=dict(AC=0))
    a = callset['variants/AC']
    eq_((9,), a.shape)
    eq_(False, a[0])
    eq_(True, a[6])

    callset = read_vcf(vcf_path, fields=['AC'], numbers=dict(AC=1))
    a = callset['variants/AC']
    eq_((9,), a.shape)
    eq_(-1, a[0])
    eq_(3, a[6])

    callset = read_vcf(vcf_path, fields=['AC'], numbers=dict(AC=2))
    a = callset['variants/AC']
    eq_((9, 2), a.shape)
    eq_(-1, a[0, 0])
    eq_(-1, a[0, 1])
    eq_(3, a[6, 0])
    eq_(1, a[6, 1])

    callset = read_vcf(vcf_path, fields='AF', numbers=dict(AF=1))
    a = callset['variants/AF']
    eq_((9,), a.shape)
    eq_(0.5, a[2])
    assert_almost_equal(0.333, a[4])

    callset = read_vcf(vcf_path, fields='AF', numbers=dict(AF=2))
    a = callset['variants/AF']
    eq_((9, 2), a.shape)
    eq_(0.5, a[2, 0])
    assert np.isnan(a[2, 1])
    assert_almost_equal(0.333, a[4, 0])
    assert_almost_equal(0.667, a[4, 1])

    callset = read_vcf(vcf_path, fields=['HQ'], numbers=dict(HQ=1))
    a = callset['calldata/HQ']
    eq_((9, 3), a.shape)
    eq_(10, a[0, 0])
    eq_(51, a[2, 0])
    eq_(-1, a[6, 0])

    callset = read_vcf(vcf_path, fields=['HQ'], numbers=dict(HQ=2))
    a = callset['calldata/HQ']
    eq_((9, 3, 2), a.shape)
    eq_((10, 15), tuple(a[0, 0]))
    eq_((51, 51), tuple(a[2, 0]))
    eq_((-1, -1), tuple(a[6, 0]))


def test_alt_number():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')

    callset = read_vcf(vcf_path, fields=['ALT', 'AC', 'AF'], alt_number=2)
    a = callset['variants/ALT']
    eq_((9, 2), a.shape)
    a = callset['variants/AC']
    eq_((9, 2), a.shape)
    a = callset['variants/AF']
    eq_((9, 2), a.shape)

    callset = read_vcf(vcf_path, fields=['ALT', 'AC', 'AF'], alt_number=1)
    a = callset['variants/ALT']
    eq_((9,), a.shape)
    a = callset['variants/AC']
    eq_((9,), a.shape)
    a = callset['variants/AF']
    eq_((9,), a.shape)

    callset = read_vcf(vcf_path, fields=['ALT', 'AC', 'AF'], alt_number=5)
    a = callset['variants/ALT']
    eq_((9, 5), a.shape)
    a = callset['variants/AC']
    eq_((9, 5), a.shape)
    a = callset['variants/AF']
    eq_((9, 5), a.shape)

    # can override
    callset = read_vcf(vcf_path, fields=['ALT', 'AC', 'AF'],
                       alt_number=5, numbers={'ALT': 2, 'AC': 4})
    a = callset['variants/ALT']
    eq_((9, 2), a.shape)
    a = callset['variants/AC']
    eq_((9, 4), a.shape)
    a = callset['variants/AF']
    eq_((9, 5), a.shape)


def test_read_region():

    for vcf_path in (os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf.gz'),
                     os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')):
        for tabix in 'tabix', None, 'foobar':

            region = '19'
            callset = read_vcf(vcf_path, region=region, tabix=tabix)
            chrom = callset['variants/CHROM']
            pos = callset['variants/POS']
            eq_(2, len(chrom))
            assert isinstance(chrom, np.ndarray)
            assert np.all(chrom == '19')
            eq_(2, len(pos))
            assert_array_equal([111, 112], pos)

            region = '20'
            callset = read_vcf(vcf_path, region=region, tabix=tabix)
            chrom = callset['variants/CHROM']
            pos = callset['variants/POS']
            eq_(6, len(chrom))
            assert isinstance(chrom, np.ndarray)
            assert np.all(chrom == '20')
            eq_(6, len(pos))
            assert_array_equal([14370, 17330, 1110696, 1230237, 1234567, 1235237], pos)

            region = 'X'
            callset = read_vcf(vcf_path, region=region, tabix=tabix)
            chrom = callset['variants/CHROM']
            pos = callset['variants/POS']
            eq_(1, len(chrom))
            assert isinstance(chrom, np.ndarray)
            assert np.all(chrom == 'X')
            eq_(1, len(pos))
            assert_array_equal([10], pos)

            region = 'Y'
            callset = read_vcf(vcf_path, region=region, tabix=tabix)
            assert callset is None

            region = '20:1-100000'
            callset = read_vcf(vcf_path, region=region, tabix=tabix)
            chrom = callset['variants/CHROM']
            pos = callset['variants/POS']
            eq_(2, len(chrom))
            assert isinstance(chrom, np.ndarray)
            assert np.all(chrom == '20')
            eq_(2, len(pos))
            assert_array_equal([14370, 17330], pos)

            region = '20:1000000-1233000'
            callset = read_vcf(vcf_path, region=region, tabix=tabix)
            chrom = callset['variants/CHROM']
            pos = callset['variants/POS']
            eq_(2, len(chrom))
            assert isinstance(chrom, np.ndarray)
            assert np.all(chrom == '20')
            eq_(2, len(pos))
            assert_array_equal([1110696, 1230237], pos)

            region = '20:1233000-2000000'
            callset = read_vcf(vcf_path, region=region, tabix=tabix)
            chrom = callset['variants/CHROM']
            pos = callset['variants/POS']
            eq_(2, len(chrom))
            assert isinstance(chrom, np.ndarray)
            assert np.all(chrom == '20')
            eq_(2, len(pos))
            assert_array_equal([1234567, 1235237], pos)


def test_read_region_unsorted():
    # Test behaviour when data are not sorted by chromosome or position and tabix is
    # not available.

    fn = os.path.join(os.path.dirname(__file__), 'data', 'unsorted.vcf')
    tabix = None

    region = '19'
    callset = read_vcf(fn, region=region, tabix=tabix)
    chrom = callset['variants/CHROM']
    pos = callset['variants/POS']
    eq_(2, len(chrom))
    assert isinstance(chrom, np.ndarray)
    assert np.all(chrom == '19')
    eq_(2, len(pos))
    assert_array_equal([111, 112], pos)

    region = '20'
    callset = read_vcf(fn, region=region, tabix=tabix)
    chrom = callset['variants/CHROM']
    pos = callset['variants/POS']
    eq_(6, len(chrom))
    assert isinstance(chrom, np.ndarray)
    assert np.all(chrom == '20')
    eq_(6, len(pos))
    assert_array_equal([14370, 1230237, 1234567, 1235237, 17330, 1110696], pos)

    region = 'X'
    callset = read_vcf(fn, region=region, tabix=tabix)
    chrom = callset['variants/CHROM']
    pos = callset['variants/POS']
    eq_(1, len(chrom))
    assert isinstance(chrom, np.ndarray)
    assert np.all(chrom == 'X')
    eq_(1, len(pos))
    assert_array_equal([10], pos)

    region = 'Y'
    callset = read_vcf(fn, region=region, tabix=tabix)
    assert callset is None

    region = '20:1-100000'
    callset = read_vcf(fn, region=region, tabix=tabix)
    chrom = callset['variants/CHROM']
    pos = callset['variants/POS']
    eq_(2, len(chrom))
    assert isinstance(chrom, np.ndarray)
    assert np.all(chrom == '20')
    eq_(2, len(pos))
    assert_array_equal([14370, 17330], pos)

    region = '20:1000000-1233000'
    callset = read_vcf(fn, region=region, tabix=tabix)
    chrom = callset['variants/CHROM']
    pos = callset['variants/POS']
    eq_(2, len(chrom))
    assert isinstance(chrom, np.ndarray)
    assert np.all(chrom == '20')
    eq_(2, len(pos))
    assert_array_equal([1230237, 1110696], pos)

    region = '20:1233000-2000000'
    callset = read_vcf(fn, region=region, tabix=tabix)
    chrom = callset['variants/CHROM']
    pos = callset['variants/POS']
    eq_(2, len(chrom))
    assert isinstance(chrom, np.ndarray)
    assert np.all(chrom == '20')
    eq_(2, len(pos))
    assert_array_equal([1234567, 1235237], pos)


def test_read_samples():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')

    for samples in ['NA00001', 'NA00003'], [0, 2], ['NA00003', 'NA00001'], [2, 'NA00001']:
        callset = read_vcf(vcf_path, fields=['samples', 'GT'], samples=samples)
        assert_list_equal(['NA00001', 'NA00003'], callset['samples'].astype('U').tolist())
        gt = callset['calldata/GT']
        eq_((9, 2, 2), gt.shape)
        eq_((0, 0), tuple(gt[2, 0]))
        eq_((1, 1), tuple(gt[2, 1]))
        eq_((1, 2), tuple(gt[4, 0]))
        eq_((2, 2), tuple(gt[4, 1]))

    for samples in ['NA00002'], [1]:
        callset = read_vcf(vcf_path, fields=['samples', 'GT'], samples=samples)
        assert_list_equal(['NA00002'], callset['samples'].astype('U').tolist())
        gt = callset['calldata/GT']
        eq_((9, 1, 2), gt.shape)
        eq_((1, 0), tuple(gt[2, 0]))
        eq_((2, 1), tuple(gt[4, 0]))


def test_read_empty():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'empty.vcf')
    callset = read_vcf(vcf_path)
    assert callset is None


def test_ann():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'ann.vcf')

    # all ANN fields
    callset = read_vcf(vcf_path, fields=['ANN'], transformers=[ANNTransformer()])
    assert_list_equal(sorted(['variants/ANN_Allele',
                              'variants/ANN_Annotation',
                              'variants/ANN_Annotation_Impact',
                              'variants/ANN_Gene_Name',
                              'variants/ANN_Gene_ID',
                              'variants/ANN_Feature_Type',
                              'variants/ANN_Feature_ID',
                              'variants/ANN_Transcript_BioType',
                              'variants/ANN_Rank',
                              'variants/ANN_HGVS_c',
                              'variants/ANN_HGVS_p',
                              'variants/ANN_cDNA_pos',
                              'variants/ANN_cDNA_length',
                              'variants/ANN_CDS_pos',
                              'variants/ANN_CDS_length',
                              'variants/ANN_AA_pos',
                              'variants/ANN_AA_length',
                              'variants/ANN_Distance'
                              ]),
                      sorted(callset.keys()))
    a = callset['variants/ANN_Allele']
    eq_((3,), a.shape)
    eq_(np.dtype('object'), a.dtype)
    assert_array_equal(['T', '', 'T'], a)
    a = callset['variants/ANN_Annotation']
    eq_((3,), a.shape)
    eq_(np.dtype('object'), a.dtype)
    assert_array_equal(['intergenic_region', '', 'missense_variant'], a)
    a = callset['variants/ANN_Annotation_Impact']
    eq_((3,), a.shape)
    eq_(np.dtype('object'), a.dtype)
    assert_array_equal(['MODIFIER', '', 'MODERATE'], a)
    a = callset['variants/ANN_Gene_Name']
    eq_((3,), a.shape)
    eq_(np.dtype('object'), a.dtype)
    assert_array_equal(['AGAP004677', '', 'AGAP005273'], a)
    a = callset['variants/ANN_Gene_ID']
    eq_((3,), a.shape)
    eq_(np.dtype('object'), a.dtype)
    assert_array_equal(['AGAP004677', '', 'AGAP005273'], a)
    a = callset['variants/ANN_Feature_Type']
    eq_((3,), a.shape)
    eq_(np.dtype('object'), a.dtype)
    assert_array_equal(['intergenic_region', '', 'transcript'], a)
    a = callset['variants/ANN_Feature_ID']
    eq_((3,), a.shape)
    eq_(np.dtype('object'), a.dtype)
    assert_array_equal(['AGAP004677', '', 'AGAP005273-RA'], a)
    a = callset['variants/ANN_Transcript_BioType']
    eq_(np.dtype('object'), a.dtype)
    eq_((3,), a.shape)
    assert_array_equal(['', '', 'VectorBase'], a)
    eq_(np.dtype('object'), a.dtype)
    a = callset['variants/ANN_Rank']
    eq_((3,), a.shape)
    eq_(np.dtype('int8'), a.dtype)
    assert_array_equal([-1, -1, 1], a[:])
    a = callset['variants/ANN_HGVS_c']
    eq_((3,), a.shape)
    eq_(np.dtype('object'), a.dtype)
    assert_array_equal(['', '', '17A>T'], a)
    a = callset['variants/ANN_HGVS_p']
    eq_((3,), a.shape)
    eq_(np.dtype('object'), a.dtype)
    assert_array_equal(['', '', 'Asp6Val'], a)
    a = callset['variants/ANN_cDNA_pos']
    eq_((3,), a.shape)
    eq_(np.dtype('int32'), a.dtype)
    assert_array_equal([-1, -1, 17], a)
    a = callset['variants/ANN_cDNA_length']
    eq_((3,), a.shape)
    eq_(np.dtype('int32'), a.dtype)
    assert_array_equal([-1, -1, 4788], a)
    a = callset['variants/ANN_CDS_pos']
    eq_((3,), a.shape)
    eq_(np.dtype('int32'), a.dtype)
    assert_array_equal([-1, -1, 17], a)
    a = callset['variants/ANN_CDS_length']
    eq_((3,), a.shape)
    eq_(np.dtype('int32'), a.dtype)
    assert_array_equal([-1, -1, 4788], a)
    a = callset['variants/ANN_AA_pos']
    eq_((3,), a.shape)
    eq_(np.dtype('int32'), a.dtype)
    assert_array_equal([-1, -1, 6], a)
    a = callset['variants/ANN_AA_length']
    eq_((3,), a.shape)
    eq_(np.dtype('int32'), a.dtype)
    assert_array_equal([-1, -1, 1596], a)
    a = callset['variants/ANN_Distance']
    eq_((3,), a.shape)
    eq_(np.dtype('int32'), a.dtype)
    assert_array_equal([3000, -1, -1], a)

    # numbers=2
    callset = read_vcf(vcf_path, fields=['ANN'], numbers={'ANN': 2},
                       transformers=[ANNTransformer()])
    a = callset['variants/ANN_Allele']
    eq_((3, 2), a.shape)
    eq_(np.dtype('object'), a.dtype)
    assert_array_equal(['T', ''], a[0])
    assert_array_equal(['', ''], a[1])
    assert_array_equal(['T', 'G'], a[2])
    a = callset['variants/ANN_cDNA_pos']
    eq_((3, 2), a.shape)
    eq_(np.dtype('int32'), a.dtype)
    assert_array_equal([-1, -1, 17], a[:, 0])
    assert_array_equal([-1, -1, 12], a[:, 1])
    a = callset['variants/ANN_cDNA_length']
    eq_((3, 2), a.shape)
    eq_(np.dtype('int32'), a.dtype)
    assert_array_equal([-1, -1, 4788], a[:, 0])
    assert_array_equal([-1, -1, 4768], a[:, 1])

    # choose fields and types
    transformers = [
        ANNTransformer(
            fields=['Allele', 'ANN_HGVS_c', 'variants/ANN_cDNA_pos'],
            types={'Allele': 'S12',
                   'ANN_HGVS_c': 'S20',
                   'variants/ANN_cDNA_pos': 'i8'})
    ]
    callset = read_vcf(vcf_path, fields=['ANN'], transformers=transformers)
    assert_list_equal(sorted(['variants/ANN_Allele',
                              'variants/ANN_HGVS_c',
                              'variants/ANN_cDNA_pos']),
                      sorted(callset.keys()))
    a = callset['variants/ANN_Allele']
    eq_((3,), a.shape)
    eq_(np.dtype('S12'), a.dtype)
    assert_array_equal([b'T', b'', b'T'], a)
    a = callset['variants/ANN_HGVS_c']
    eq_((3,), a.shape)
    eq_(np.dtype('S20'), a.dtype)
    assert_array_equal([b'', b'', b'17A>T'], a)
    a = callset['variants/ANN_cDNA_pos']
    eq_((3,), a.shape)
    eq_(np.dtype('i8'), a.dtype)
    assert_array_equal([-1, -1, 17], a)


def test_format_inconsistencies():

    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\tfoo\tA\tC\t1.2\t.\t.\tGT:GQ\t0/1:12\t1/2\t2/3:34:67,89\t\n"
        b"2R\t34\tbar\tC\tG\t3.4\t.\t.\tGT\t./.\t\t3/3:45\t1/2:11:55,67\n"
    )

    input_file = io.BytesIO(input_data)
    callset = read_vcf(input_file, fields=['calldata/GT', 'calldata/GQ'])
    gt = callset['calldata/GT']
    eq_((2, 4, 2), gt.shape)
    assert_array_equal([[0, 1], [1, 2], [2, 3], [-1, -1]], gt[0])
    assert_array_equal([[-1, -1], [-1, -1], [3, 3], [1, 2]], gt[1])
    gq = callset['calldata/GQ']
    eq_((2, 4), gq.shape)
    assert_array_equal([12, -1, 34, -1], gq[0])
    assert_array_equal([-1, -1, -1, -1], gq[1])


# noinspection PyTypeChecker
def test_warnings():

    warnings.resetwarnings()
    warnings.simplefilter('error')

    # empty CHROM
    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"\t12\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\n"
    )
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data))

    # empty POS
    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\n"
    )
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data))

    # dodgy POS
    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\taaa\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\n"
    )
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data))

    # dodgy POS
    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12aaa\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\t.\n"
    )
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data))

    # dodgy QUAL
    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\t.\t.\t.\taaa\t.\t.\t.\t.\t.\t.\t.\n"
    )
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data))

    # dodgy QUAL
    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\t.\t.\t.\t1.2aaa\t.\t.\t.\t.\t.\t.\t.\n"
    )
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data))

    # empty QUAL - no warning
    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\t.\t.\t.\t\t.\t.\t.\t.\t.\t.\t.\n"
    )
    read_vcf(io.BytesIO(input_data))

    # empty FILTER - no warning
    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\t.\t.\t.\t.\t\t.\t.\t.\t.\t.\t.\n"
    )
    read_vcf(io.BytesIO(input_data))

    # empty INFO - no warning
    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\t.\t.\t.\t.\t.\t\t.\t.\t.\t.\t.\n"
    )
    read_vcf(io.BytesIO(input_data))

    # empty FORMAT - no warning
    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\t.\t.\t.\t.\t.\t.\t\t.\t.\t.\t.\n"
    )
    read_vcf(io.BytesIO(input_data))

    # dodgy calldata (integer)
    input_data = (
        b'##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\t.\t.\t.\t.\t.\t.\tGT\t0/1\taa/bb\t.\t.\n"
    )
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data), fields=['calldata/GT'])

    # dodgy calldata (integer)
    input_data = (
        b'##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\t.\t.\t.\t.\t.\t.\tGT\t0/1\t12aa/22\t.\t.\n"
    )
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data), fields=['calldata/GT'])

    # dodgy calldata (float)
    input_data = (
        b'##FORMAT=<ID=MQ,Number=1,Type=Float,Description="Mapping Quality">\n'
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\t.\t.\t.\t.\t.\t.\tMQ\t.\t12.3\taaa\t.\n"
    )
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data), fields=['calldata/MQ'])

    # dodgy calldata (float)
    input_data = (
        b'##FORMAT=<ID=MQ,Number=1,Type=Float,Description="Mapping Quality">\n'
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\t.\t.\t.\t.\t.\t.\tMQ\t.\t12.3\t34.5aaa\t.\n"
    )
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data), fields=['calldata/MQ'])

    # dodgy INFO (missing key)
    input_data = (
        b'##INFO=<ID=MQ,Number=1,Type=Float,Description="Mapping Quality">\n'
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\t.\t.\t.\t.\t.\tfoo=qux;MQ=12\t.\t.\t.\t.\t.\n"
        b"2L\t34\t.\t.\t.\t.\t.\tfoo=bar;=34;baz\t.\t.\t.\t.\t.\n"
    )
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data), fields=['variants/MQ'])

    # INFO not declared in header
    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\tfoo\tA\tC,T\t12.3\tPASS\tfoo=bar\tGT:GQ\t0/0:99\t0/1:12\t./.:.\t.\n"
    )
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data), fields=['variants/foo'])

    # FORMAT not declared in header
    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\tfoo\tA\tC,T\t12.3\tPASS\tfoo=bar\tGT:GQ\t0/0:99\t0/1:12\t./.:.\t.\n"
    )
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data), fields=['calldata/GT'])
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data), fields=['calldata/GQ'])

    warnings.resetwarnings()
    warnings.simplefilter('always')


def test_missing_headers():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'test14.vcf')

    # INFO DP not declared
    callset = read_vcf(vcf_path, fields=['DP'], types={'DP': 'String'})
    a = callset['variants/DP']
    eq_('14', a[2])  # default type is string
    callset = read_vcf(vcf_path, fields=['DP'], types={'DP': 'Integer'})
    a = callset['variants/DP']
    eq_(14, a[2])
    # what about a field which isn't present at all?
    callset = read_vcf(vcf_path, fields=['FOO'])
    eq_('', callset['variants/FOO'][2])  # default missing value for string field

    # FORMAT field DP not declared in VCF header
    callset = read_vcf(vcf_path, fields=['calldata/DP'],
                       types={'calldata/DP': 'Integer'})
    eq_(1, callset['calldata/DP'][2, 0])


def test_extra_samples():
    # more calldata samples than samples declared in header
    path = os.path.join(os.path.dirname(__file__), 'data', 'test48b.vcf')
    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS2\tS1\tS3\tS4\n"
        b"2L\t12\t.\t.\t.\t.\t.\t.\tGT:GQ\t0/0:34\t0/1:45\t1/1:56\t1/2:99\t2/3:101\n"
    )

    warnings.resetwarnings()
    warnings.simplefilter('error')
    with assert_raises(UserWarning):
        read_vcf(path)
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data), fields=['calldata/GT', 'calldata/GQ'])

    warnings.resetwarnings()
    warnings.simplefilter('always')
    # try again without raising warnings to check data
    callset = read_vcf(io.BytesIO(input_data), fields=['calldata/GT', 'calldata/GQ'])
    eq_((1, 4, 2), callset['calldata/GT'].shape)
    callset = read_vcf(path)
    eq_((9, 2, 2), callset['calldata/GT'].shape)


# noinspection PyTypeChecker
def test_no_samples():

    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\n"
        b"2L\t12\tfoo\tA\tC,T\t12.3\tPASS\tfoo=bar\tGT:GQ\t0/0:99\t0/1:12\t./.:.\t.\n"
    )

    callset = read_vcf(io.BytesIO(input_data),
                       fields=['calldata/GT', 'calldata/GQ', 'samples', 'POS'])

    assert 'variants/POS' in callset
    assert 'samples' not in callset
    assert 'calldata/GT' not in callset
    assert 'calldata/GQ' not in callset

    h5_path = os.path.join(tempdir, 'sample.h5')
    if os.path.exists(h5_path):
        os.remove(h5_path)
    vcf_to_hdf5(io.BytesIO(input_data), h5_path,
                fields=['calldata/GT', 'calldata/GQ', 'samples', 'POS'])
    with h5py.File(h5_path, mode='r') as callset:
        assert 'variants/POS' in callset
        assert 'samples' not in callset
        assert 'calldata/GT' not in callset
        assert 'calldata/GQ' not in callset

    zarr_path = os.path.join(tempdir, 'sample.zarr')
    if os.path.exists(zarr_path):
        shutil.rmtree(zarr_path)
    vcf_to_zarr(io.BytesIO(input_data), zarr_path,
                fields=['calldata/GT', 'calldata/GQ', 'samples', 'POS'])
    callset = zarr.open_group(zarr_path, mode='r')
    assert 'variants/POS' in callset
    assert 'samples' not in callset
    assert 'calldata/GT' not in callset
    assert 'calldata/GQ' not in callset


def test_computed_fields():

    input_data = (b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\n"
                  b"2L\t2\t.\t.\t.\t.\t.\t.\t.\n"
                  b"2L\t4\t.\t.\tG\t.\t.\t.\t.\n"
                  b"2L\t12\t.\tA\t.\t.\t.\t.\t.\n"
                  b"2L\t34\t.\tC\tT\t.\t.\t.\t.\n"
                  b"3R\t45\t.\tG\tA,T\t.\t.\t.\t.\n"
                  b"3R\t47\t.\tG\tC,T,*\t.\t.\t.\t.\n"
                  b"3R\t56\t.\tG\tA,GTAC\t.\t.\t.\t.\n"
                  b"3R\t56\t.\tCATG\tC,GATG\t.\t.\t.\t.\n"
                  b"3R\t56\t.\tGTAC\tATAC,GTACTACTAC,G,GTACA,GTA\t.\t.\t.\t.\n")

    for string_dtype in 'S20', 'object':

        callset = read_vcf(io.BytesIO(input_data),
                           fields='*',
                           numbers={'ALT': 5},
                           types={'REF': string_dtype, 'ALT': string_dtype})

        a = callset['variants/ALT']
        eq_((9, 5), a.shape)
        e = np.array([[b'', b'', b'', b'', b''],
                      [b'G', b'', b'', b'', b''],
                      [b'', b'', b'', b'', b''],
                      [b'T', b'', b'', b'', b''],
                      [b'A', b'T', b'', b'', b''],
                      [b'C', b'T', b'*', b'', b''],
                      [b'A', b'GTAC', b'', b'', b''],
                      [b'C', b'GATG', b'', b'', b''],
                      [b'ATAC', b'GTACTACTAC', b'G', b'GTACA', b'GTA']])
        if a.dtype.kind == 'O':
            e = e.astype('U').astype(object)
        assert_array_equal(e, a)

        a = callset['variants/numalt']
        eq_((9,), a.shape)
        assert_array_equal([0, 1, 0, 1, 2, 3, 2, 2, 5], a)

        a = callset['variants/altlen']
        eq_((9, 5), a.shape)
        e = np.array([[0, 0, 0, 0, 0],
                      [1, 0, 0, 0, 0],
                      [0, 0, 0, 0, 0],
                      [0, 0, 0, 0, 0],
                      [0, 0, 0, 0, 0],
                      [0, 0, -1, 0, 0],
                      [0, 3, 0, 0, 0],
                      [-3, 0, 0, 0, 0],
                      [0, 6, -3, 1, -1]])
        assert_array_equal(e, a)

        a = callset['variants/is_snp']
        eq_((9,), a.shape)
        eq_(np.dtype(bool), a.dtype)
        assert_array_equal([False, False, False, True, True, False, False, False, False],
                           a)

        # test is_snp with reduced ALT number
        callset = read_vcf(io.BytesIO(input_data),
                           fields='*',
                           numbers={'ALT': 1},
                           types={'REF': string_dtype, 'ALT': string_dtype})

        a = callset['variants/ALT']
        eq_((9,), a.shape)
        e = np.array([b'', b'G', b'', b'T', b'A', b'C', b'A', b'C', b'ATAC'])
        if a.dtype.kind == 'O':
            e = e.astype('U').astype(object)
        assert_array_equal(e, a)

        a = callset['variants/numalt']
        eq_((9,), a.shape)
        assert_array_equal([0, 1, 0, 1, 2, 3, 2, 2, 5], a)

        a = callset['variants/altlen']
        eq_((9,), a.shape)
        e = np.array([0, 1, 0, 0, 0, 0, 0, -3, 0])
        assert_array_equal(e, a)

        a = callset['variants/is_snp']
        eq_((9,), a.shape)
        eq_(np.dtype(bool), a.dtype)
        assert_array_equal([False, False, False, True, True, False, False, False, False],
                           a)


def test_genotype_ac():

    input_data = (
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\tS2\tS3\n"
        b"2L\t12\t.\tA\t.\t.\t.\t.\tGT:GQ\t0/0/0:11\t0/1/2:12\t././.:.\n"
        b"2L\t34\t.\tC\tT\t.\t.\t.\tGT:GQ\t0/1/2:22\t3/3/.:33\t.\n"
        b"3R\t45\t.\tG\tA,T\t.\t.\t.\tGT:GQ\t0/1:.\t3:12\t\n"
        b"X\t55\t.\tG\tA,T\t.\t.\t.\tGT:GQ\t0/1/1/3/4:.\t1/1/2/2/4/4/5:12\t0/0/1/2/3/./4\n"
    )

    for t in 'i1', 'i2', 'i4', 'i8', 'u1', 'u2', 'u4', 'u8':
        callset = read_vcf(io.BytesIO(input_data),
                           fields=['calldata/GT'],
                           numbers={'calldata/GT': 4},
                           types={'calldata/GT': 'genotype_ac/' + t})
        e = np.array([[[3, 0, 0, 0], [1, 1, 1, 0], [0, 0, 0, 0]],
                      [[1, 1, 1, 0], [0, 0, 0, 2], [0, 0, 0, 0]],
                      [[1, 1, 0, 0], [0, 0, 0, 1], [0, 0, 0, 0]],
                      [[1, 2, 0, 1], [0, 2, 2, 0], [2, 1, 1, 1]]], dtype=t)
        a = callset['calldata/GT']
        eq_(e.dtype, a.dtype)
        assert_array_equal(e, a)

    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'test63.vcf')
    callset = read_vcf(vcf_path, fields='GT', numbers={'GT': 3},
                       types={'GT': 'genotype_ac/i1'})
    e = np.array([
        [(2, 0, 0), (3, 0, 0), (1, 0, 0)],
        [(0, 1, 0), (1, 1, 0), (1, 1, 1)],
        [(0, 0, 0), (0, 0, 0), (0, 0, 0)],
        [(0, 0, 0), (0, 0, 0), (0, 0, 0)],
    ])
    a = callset['calldata/GT']
    assert_array_equal(e, a)


def test_region_truncate():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'test54.vcf.gz')
    for tabix in 'tabix', None:
        callset = read_vcf(vcf_path, region='chr1:10-100', tabix=tabix)
        pos = callset['variants/POS']
        eq_(2, pos.shape[0])
        assert_array_equal([20, 30], pos)


def test_errors():

    # try to open a directory
    path = '.'
    if PY2:
        excls = IOError
    else:
        excls = OSError
    with assert_raises(excls):
        read_vcf(path)

    if PY2:
        excls = IOError
    else:
        excls = FileNotFoundError

    # try to open a file that doesn't exist
    path = 'doesnotexist.vcf'
    with assert_raises(excls):
        read_vcf(path)

    # try to open a file that doesn't exist
    path = 'doesnotexist.vcf.gz'
    with assert_raises(excls):
        read_vcf(path)

    # file is nothing like a VCF (has no header)
    path = os.path.join(os.path.dirname(__file__), 'data', 'test48a.vcf')
    with assert_raises(RuntimeError):
        read_vcf(path)


def test_dup_headers():

    warnings.resetwarnings()
    warnings.simplefilter('error')

    # dup FILTER
    input_data = b"""##fileformat=VCFv4.1
##FILTER=<ID=s50,Description="Less than 50% of samples have data">
##FILTER=<ID=s50,Description="Less than 50% of samples have data">
##INFO=<ID=DP,Number=1,Type=Integer,Description="Total Depth">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
##FORMAT=<ID=AD,Number=A,Type=Integer,Description="Allele Depths">
##FORMAT=<ID=ZZ,Number=1,Type=String,Description="ZZ">
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO	FORMAT	test1	test2	test3	test4
chr1	1	.	A	G	.	PASS	DP=2	GT:AD	0:1,0	.:1,0	0:0,0	.:0,0
chr1	2	.	A	G	.	PASS	DP=2	GT:AD:ZZ	0:1,0:dummy	0:1,0	0:0,0	.:0,0
chr1	3	.	A	G	.	PASS	DP=2	GT:AD:ZZ	0:1,0:dummy	1:1,0	.	./.
"""
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data))

    # dup INFO
    input_data = b"""##fileformat=VCFv4.1
##FILTER=<ID=s50,Description="Less than 50% of samples have data">
##INFO=<ID=DP,Number=1,Type=Integer,Description="Total Depth">
##INFO=<ID=DP,Number=1,Type=Integer,Description="Total Depth">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
##FORMAT=<ID=AD,Number=A,Type=Integer,Description="Allele Depths">
##FORMAT=<ID=ZZ,Number=1,Type=String,Description="ZZ">
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO	FORMAT	test1	test2	test3	test4
chr1	1	.	A	G	.	PASS	DP=2	GT:AD	0:1,0	.:1,0	0:0,0	.:0,0
chr1	2	.	A	G	.	PASS	DP=2	GT:AD:ZZ	0:1,0:dummy	0:1,0	0:0,0	.:0,0
chr1	3	.	A	G	.	PASS	DP=2	GT:AD:ZZ	0:1,0:dummy	1:1,0	.	./.
"""
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data))

    # dup FORMAT
    input_data = b"""##fileformat=VCFv4.1
##FILTER=<ID=s50,Description="Less than 50% of samples have data">
##INFO=<ID=DP,Number=1,Type=Integer,Description="Total Depth">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
##FORMAT=<ID=AD,Number=A,Type=Integer,Description="Allele Depths">
##FORMAT=<ID=AD,Number=A,Type=Integer,Description="Allele Depths">
##FORMAT=<ID=ZZ,Number=1,Type=String,Description="ZZ">
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO	FORMAT	test1	test2	test3	test4
chr1	1	.	A	G	.	PASS	DP=2	GT:AD	0:1,0	.:1,0	0:0,0	.:0,0
chr1	2	.	A	G	.	PASS	DP=2	GT:AD:ZZ	0:1,0:dummy	0:1,0	0:0,0	.:0,0
chr1	3	.	A	G	.	PASS	DP=2	GT:AD:ZZ	0:1,0:dummy	1:1,0	.	./.
"""
    with assert_raises(UserWarning):
        read_vcf(io.BytesIO(input_data))

    warnings.resetwarnings()
    warnings.simplefilter('always')


def test_override_vcf_type():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'test4.vcf')
    callset = read_vcf(vcf_path, fields=['MQ0FractionTest'])
    eq_(0, callset['variants/MQ0FractionTest'][2])
    callset = read_vcf(vcf_path, fields=['MQ0FractionTest'],
                       types={'MQ0FractionTest': 'Float'})
    assert_almost_equal(0.03, callset['variants/MQ0FractionTest'][2], places=6)


def test_header_overrides_default_vcf_type():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'test176.vcf')
    callset = read_vcf(vcf_path, fields='*')
    gq = callset['calldata/GQ']
    eq_('f', gq.dtype.kind)
    assert np.isnan(gq[0, 0])
    assert_almost_equal(48.2, gq[2, 0], places=2)
    assert_almost_equal(48.1, gq[2, 1], places=2)
    assert_almost_equal(43.9, gq[2, 2], places=2)
    assert_almost_equal(49., gq[3, 0], places=2)
    assert_almost_equal(3., gq[3, 1], places=2)
    assert_almost_equal(41., gq[3, 2], places=2)


def test_missing_calldata():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'test1.vcf')
    callset = read_vcf(vcf_path, fields='calldata/*', numbers={'AD': 2})
    gt = callset['calldata/GT']
    ad = callset['calldata/AD']
    eq_((-1, -1), tuple(gt[0, 1]))
    eq_((1, 0), tuple(ad[0, 1]))
    eq_((-1, -1), tuple(gt[2, 2]))
    eq_((-1, -1), tuple(ad[2, 2]))
    eq_((-1, -1), tuple(gt[2, 3]))
    eq_((-1, -1), tuple(ad[2, 3]))


def test_calldata_cleared():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'test32.vcf')
    callset = read_vcf(vcf_path, fields=['calldata/GT', 'calldata/DP', 'calldata/GQ'])
    gt = callset['calldata/GT']
    dp = callset['calldata/DP']
    gq = callset['calldata/GQ']
    eq_((0, 0), tuple(gt[0, 3]))
    eq_(8, dp[0, 3])
    eq_(3, gq[0, 3])
    eq_((-1, -1), tuple(gt[1, 3]))
    eq_(-1, dp[1, 3])
    eq_(-1, gq[1, 3])


def test_calldata_quirks():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'test1.vcf')
    callset = read_vcf(vcf_path, fields=['AD', 'GT'], numbers={'AD': 2})
    gt = callset['calldata/GT']
    ad = callset['calldata/AD']
    e = np.array([[-1, -1], [0, -1], [1, -1]])
    assert_array_equal(e, gt[:, 1])
    e = np.array([[1, 0], [1, 0], [1, 0]])
    assert_array_equal(e, ad[:, 1])


def test_vcf_to_npz():
    vcf_paths = [os.path.join(os.path.dirname(__file__), 'data', x)
                 for x in ['sample.vcf', 'sample.vcf.gz']]
    npz_path = os.path.join(tempdir, 'sample.npz')
    region_values = None, '20', '20:10000-20000', 'Y'
    tabix_values = 'tabix', None
    samples_values = None, ['NA00001', 'NA00003']
    string_type_values = 'S10', 'object'
    param_matrix = itertools.product(vcf_paths, region_values, tabix_values,
                                     samples_values, string_type_values)
    for vcf_path, region, tabix, samples, string_type in param_matrix:
        types = {'CHROM': string_type, 'ALT': string_type, 'samples': string_type}
        expected = read_vcf(vcf_path, fields='*', alt_number=2, region=region,
                            tabix=tabix, samples=samples, types=types)
        if os.path.exists(npz_path):
            os.remove(npz_path)
        vcf_to_npz(vcf_path, npz_path, fields='*', chunk_length=2, alt_number=2,
                   region=region, tabix=tabix, samples=samples, types=types)
        if expected is None:
            assert not os.path.exists(npz_path)
        else:
            actual = np.load(npz_path)
            for key in expected.keys():
                if expected[key].dtype.kind == 'f':
                    assert_array_almost_equal(expected[key], actual[key])
                else:
                    assert_array_equal(expected[key], actual[key])
            for key in actual.keys():
                assert key in expected
            actual.close()


def test_vcf_to_npz_exclude():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    npz_path = os.path.join(tempdir, 'sample.npz')
    exclude = ['variants/altlen', 'ID', 'calldata/DP']
    expected = read_vcf(vcf_path, fields='*', exclude_fields=exclude)
    if os.path.exists(npz_path):
        os.remove(npz_path)
    vcf_to_npz(vcf_path, npz_path, fields='*', exclude_fields=exclude)
    actual = np.load(npz_path)
    for key in expected.keys():
        if expected[key].dtype.kind == 'f':
            assert_array_almost_equal(expected[key], actual[key])
        else:
            assert_array_equal(expected[key], actual[key])
    for key in actual.keys():
        assert key in expected
    actual.close()


def test_vcf_to_npz_rename():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    npz_path = os.path.join(tempdir, 'sample.npz')
    rename = {'CHROM': 'variants/chromosome',
              'variants/altlen': 'spam/eggs',
              'calldata/GT': 'foo/bar'}
    expected = read_vcf(vcf_path, fields='*', rename_fields=rename)
    if os.path.exists(npz_path):
        os.remove(npz_path)
    vcf_to_npz(vcf_path, npz_path, fields='*', rename_fields=rename)
    actual = np.load(npz_path)
    for key in expected.keys():
        if expected[key].dtype.kind == 'f':
            assert_array_almost_equal(expected[key], actual[key])
        else:
            assert_array_equal(expected[key], actual[key])
    for key in actual.keys():
        assert key in expected
    actual.close()


def test_vcf_to_zarr():
    vcf_paths = [os.path.join(os.path.dirname(__file__), 'data', x)
                 for x in ['sample.vcf', 'sample.vcf.gz']]
    zarr_path = os.path.join(tempdir, 'sample.zarr')
    region_values = None, '20', '20:10000-20000', 'Y'
    tabix_values = 'tabix', None
    samples_values = None, ['NA00001', 'NA00003']
    string_type_values = 'S10', 'object'
    param_matrix = itertools.product(vcf_paths, region_values, tabix_values,
                                     samples_values, string_type_values)
    for vcf_path, region, tabix, samples, string_type in param_matrix:
        types = {'CHROM': string_type, 'ALT': string_type, 'samples': string_type}
        expected = read_vcf(vcf_path, fields='*', alt_number=2, region=region,
                            tabix=tabix, samples=samples, types=types)
        if os.path.exists(zarr_path):
            shutil.rmtree(zarr_path)
        vcf_to_zarr(vcf_path, zarr_path, fields='*', alt_number=2, chunk_length=2,
                    region=region, tabix=tabix, samples=samples, types=types)
        if expected is None:
            assert not os.path.exists(zarr_path)
        else:
            actual = zarr.open_group(zarr_path, mode='r')
            for key in expected.keys():
                e = expected[key]
                a = actual[key][:]
                compare_arrays(e, a)
                eq_(actual['variants/NS'].attrs['Description'],
                    'Number of Samples With Data')
                eq_(actual['calldata/GQ'].attrs['Description'],
                    'Genotype Quality')
            for key in actual.keys():
                if key not in {'variants', 'calldata'}:
                    assert key in expected
            for key in actual['variants'].keys():
                assert 'variants/' + key in expected
            for key in actual['calldata'].keys():
                assert 'calldata/' + key in expected


def test_vcf_to_zarr_exclude():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    zarr_path = os.path.join(tempdir, 'sample.zarr')
    exclude = ['variants/altlen', 'ID', 'calldata/DP']
    expected = read_vcf(vcf_path, fields='*', exclude_fields=exclude)
    if os.path.exists(zarr_path):
        shutil.rmtree(zarr_path)
    vcf_to_zarr(vcf_path, zarr_path, fields='*', exclude_fields=exclude)
    actual = zarr.open_group(zarr_path, mode='r')
    for key in expected.keys():
        e = expected[key]
        a = actual[key][:]
        compare_arrays(e, a)
    for key in actual.keys():
        if key not in {'variants', 'calldata'}:
            assert key in expected
    for key in actual['variants'].keys():
        assert 'variants/' + key in expected
    for key in actual['calldata'].keys():
        assert 'calldata/' + key in expected


def test_vcf_to_zarr_rename():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    zarr_path = os.path.join(tempdir, 'sample.zarr')
    rename = {'CHROM': 'variants/chromosome',
              'variants/altlen': 'spam/eggs',
              'calldata/GT': 'foo/bar'}
    expected = read_vcf(vcf_path, fields='*', rename_fields=rename)
    if os.path.exists(zarr_path):
        shutil.rmtree(zarr_path)
    vcf_to_zarr(vcf_path, zarr_path, fields='*', rename_fields=rename)
    actual = zarr.open_group(zarr_path, mode='r')
    for key in expected.keys():
        e = expected[key]
        a = actual[key][:]
        compare_arrays(e, a)
    for key in actual['variants'].keys():
        assert 'variants/' + key in expected
    for key in actual['calldata'].keys():
        assert 'calldata/' + key in expected


def test_vcf_to_zarr_dup_fields_case_insensitive():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'altlen.vcf')
    zarr_path = os.path.join(tempdir, 'sample.zarr')
    with assert_raises(ValueError):
        vcf_to_zarr(vcf_path, zarr_path, fields=['ALTLEN', 'altlen'])
    with assert_raises(ValueError):
        vcf_to_zarr(vcf_path, zarr_path, fields=['variants/ALTLEN', 'variants/altlen'])
    # should be fine if renamed
    vcf_to_zarr(vcf_path, zarr_path, fields=['ALTLEN', 'altlen'],
                rename_fields={'altlen': 'variants/spam'})


def test_vcf_to_zarr_group():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf.gz')
    zarr_path = os.path.join(tempdir, 'sample.zarr')
    if os.path.exists(zarr_path):
        shutil.rmtree(zarr_path)
    chroms = ['19', '20', 'X']
    for chrom in chroms:
        vcf_to_zarr(vcf_path, zarr_path, fields='*', alt_number=2, chunk_length=2,
                    region=chrom, group=chrom)
    actual = zarr.open_group(zarr_path, mode='r')
    eq_(chroms, sorted(actual))
    for chrom in chroms:
        assert ['calldata', 'samples', 'variants'] == sorted(actual[chrom])
        expect = read_vcf(vcf_path, fields='*', alt_number=2, region=chrom)
        for key in expect.keys():
            e = expect[key]
            a = actual[chrom][key][:]
            compare_arrays(e, a)
            eq_(actual[chrom]['variants/NS'].attrs['Description'],
                'Number of Samples With Data')
            eq_(actual[chrom]['calldata/GQ'].attrs['Description'],
                'Genotype Quality')


def test_vcf_to_zarr_string_codec():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    zarr_path = os.path.join(tempdir, 'sample.zarr')
    types = {'CHROM': object, 'ALT': object, 'samples': object}
    expect = read_vcf(vcf_path, fields='*', alt_number=2, types=types)
    if os.path.exists(zarr_path):
        shutil.rmtree(zarr_path)
    vcf_to_zarr(vcf_path, zarr_path, fields='*', alt_number=2, chunk_length=2,
                types=types)
    actual = zarr.open_group(zarr_path, mode='r')
    for key in expect.keys():
        e = expect[key]
        a = actual[key][:]
        compare_arrays(e, a)


def test_vcf_to_zarr_ann():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'ann.vcf')
    zarr_path = os.path.join(tempdir, 'ann.zarr')
    for string_type in 'S10', 'object':
        types = {'CHROM': string_type, 'ALT': string_type, 'samples': string_type}
        transformers = [ANNTransformer(fields=['Allele', 'HGVS_c', 'AA'],
                                       types={'Allele': string_type,
                                              'HGVS_c': string_type})]
        expected = read_vcf(vcf_path, fields='*', alt_number=2, types=types,
                            transformers=transformers)
        if os.path.exists(zarr_path):
            shutil.rmtree(zarr_path)
        vcf_to_zarr(vcf_path, zarr_path, fields='*', alt_number=2, chunk_length=2,
                    types=types, transformers=transformers)
        actual = zarr.open_group(zarr_path, mode='r')
        for key in expected.keys():
            compare_arrays(expected[key], actual[key][:])


def test_vcf_to_zarr_empty():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'empty.vcf')
    zarr_path = os.path.join(tempdir, 'empty.zarr')
    vcf_to_zarr(vcf_path, zarr_path)
    assert not os.path.exists(zarr_path)


def test_vcf_to_hdf5():
    vcf_paths = [os.path.join(os.path.dirname(__file__), 'data', x)
                 for x in ['sample.vcf', 'sample.vcf.gz']]
    h5_path = os.path.join(tempdir, 'sample.h5')
    region_values = None, '20', '20:10000-20000', 'Y'
    tabix_values = 'tabix', None
    samples_values = None, ['NA00001', 'NA00003']
    string_type_values = 'S10', 'object'
    param_matrix = itertools.product(vcf_paths, region_values, tabix_values,
                                     samples_values, string_type_values)
    for vcf_path, region, tabix, samples, string_type in param_matrix:
        types = {'CHROM': string_type, 'ALT': string_type, 'samples': string_type}
        expected = read_vcf(vcf_path, fields='*', alt_number=2, region=region,
                            tabix=tabix, samples=samples, types=types)
        if os.path.exists(h5_path):
            os.remove(h5_path)
        vcf_to_hdf5(vcf_path, h5_path, fields='*', alt_number=2, chunk_length=2,
                    region=region, tabix=tabix, samples=samples, types=types)
        if expected is None:
            assert not os.path.exists(h5_path)
        else:
            with h5py.File(h5_path, mode='r') as actual:
                for key in expected.keys():
                    compare_arrays(expected[key], actual[key][:])
                eq_(actual['variants/NS'].attrs['Description'],
                    'Number of Samples With Data')
                eq_(actual['calldata/GQ'].attrs['Description'],
                    'Genotype Quality')
                for key in actual.keys():
                    if key not in {'variants', 'calldata'}:
                        assert key in expected
                for key in actual['variants'].keys():
                    assert 'variants/' + key in expected
                for key in actual['calldata'].keys():
                    assert 'calldata/' + key in expected


def test_vcf_to_hdf5_exclude():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    h5_path = os.path.join(tempdir, 'sample.h5')
    exclude = ['variants/altlen', 'ID', 'calldata/DP']
    expected = read_vcf(vcf_path, fields='*', exclude_fields=exclude)
    if os.path.exists(h5_path):
        os.remove(h5_path)
    vcf_to_hdf5(vcf_path, h5_path, fields='*', exclude_fields=exclude)
    with h5py.File(h5_path, mode='r') as actual:
        for key in expected.keys():
            compare_arrays(expected[key], actual[key][:])
        for key in actual.keys():
            if key not in {'variants', 'calldata'}:
                assert key in expected
        for key in actual['variants'].keys():
            assert 'variants/' + key in expected
        for key in actual['calldata'].keys():
            assert 'calldata/' + key in expected


def test_vcf_to_hdf5_rename():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    h5_path = os.path.join(tempdir, 'sample.h5')
    rename = {'CHROM': 'variants/chromosome',
              'variants/altlen': 'spam/eggs',
              'calldata/GT': 'foo/bar'}
    expected = read_vcf(vcf_path, fields='*', rename_fields=rename)
    if os.path.exists(h5_path):
        os.remove(h5_path)
    vcf_to_hdf5(vcf_path, h5_path, fields='*', rename_fields=rename)
    with h5py.File(h5_path, mode='r') as actual:
        for key in expected.keys():
            compare_arrays(expected[key], actual[key][:])
        for key in actual['variants'].keys():
            assert 'variants/' + key in expected
        for key in actual['calldata'].keys():
            assert 'calldata/' + key in expected


def test_vcf_to_hdf5_group():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf.gz')
    h5_path = os.path.join(tempdir, 'sample.h5')
    if os.path.exists(h5_path):
        os.remove(h5_path)
    chroms = ['19', '20', 'X']
    for chrom in chroms:
        vcf_to_hdf5(vcf_path, h5_path, fields='*', alt_number=2, chunk_length=2,
                    region=chrom, group=chrom)
    with h5py.File(h5_path, mode='r') as actual:
        assert chroms == sorted(actual)
        for chrom in chroms:
            assert ['calldata', 'samples', 'variants'] == sorted(actual[chrom])
            expect = read_vcf(vcf_path, fields='*', alt_number=2, region=chrom)
            for key in expect.keys():
                e = expect[key]
                a = actual[chrom][key][:]
                compare_arrays(e, a)
                eq_(actual[chrom]['variants/NS'].attrs['Description'],
                    'Number of Samples With Data')
                eq_(actual[chrom]['calldata/GQ'].attrs['Description'],
                    'Genotype Quality')


def test_vcf_to_hdf5_ann():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'ann.vcf')
    h5_path = os.path.join(tempdir, 'ann.h5')
    for string_type in 'S10', 'object':
        types = {'CHROM': string_type, 'ALT': string_type, 'samples': string_type}
        transformers = [ANNTransformer(fields=['Allele', 'HGVS_c', 'AA'],
                                       types={'Allele': string_type,
                                              'HGVS_c': string_type})]
        expected = read_vcf(vcf_path, fields='*', types=types, transformers=transformers)
        if os.path.exists(h5_path):
            os.remove(h5_path)
        vcf_to_hdf5(vcf_path, h5_path, fields='*', chunk_length=2, types=types,
                    transformers=transformers)
        with h5py.File(h5_path, mode='r') as actual:
            for key in expected.keys():
                compare_arrays(expected[key], actual[key][:])


def test_vcf_to_hdf5_vlen():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    h5_path = os.path.join(tempdir, 'sample.h5')
    fields = ['CHROM', 'ID', 'samples']
    for string_type in 'S10', 'object':
        types = {'CHROM': string_type, 'ID': string_type, 'samples': string_type}
        expect = read_vcf(vcf_path, fields=fields, alt_number=2, types=types)
        if os.path.exists(h5_path):
            os.remove(h5_path)
        vcf_to_hdf5(vcf_path, h5_path, fields=fields, alt_number=2, chunk_length=3,
                    types=types, vlen=False)
        with h5py.File(h5_path, mode='r') as actual:
            for key in expect.keys():
                if expect[key].dtype.kind == 'f':
                    assert_array_almost_equal(expect[key], actual[key][:])
                elif expect[key].dtype.kind == 'O':
                    # strings always stored as fixed length if vlen=False
                    eq_('S', actual[key].dtype.kind)
                    assert_array_equal(expect[key].astype('S'), actual[key][:])
                else:
                    assert_array_equal(expect[key], actual[key][:])


def test_vcf_to_hdf5_empty():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'empty.vcf')
    h5_path = os.path.join(tempdir, 'empty.h5')
    vcf_to_hdf5(vcf_path, h5_path)
    assert not os.path.exists(h5_path)


def to_pandas_expectation(e):
    # expect that all string fields end up as objects with nans for missing
    if e.dtype.kind == 'S':
        e = e.astype('U').astype(object)
    if e.dtype == object:
        e[e == ''] = np.nan
    return e


def check_dataframe(callset, df):
    for k in callset:
        if k.startswith('variants/'):
            group, name = k.split('/')
            e = to_pandas_expectation(callset[k])
            if e.ndim == 1:
                compare_arrays(e, df[name].values)
            elif e.ndim == 2:
                for i in range(e.shape[1]):
                    compare_arrays(e[:, i], df['%s_%s' % (name, i + 1)])


def test_vcf_to_dataframe():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    fields = ['CHROM', 'POS', 'REF', 'ALT', 'DP', 'AC', 'GT']
    numbers = {'AC': 3}
    for string_type in 'S10', 'object':
        types = {'CHROM': string_type, 'ALT': string_type}
        callset = read_vcf(vcf_path, fields=fields, alt_number=2, numbers=numbers,
                           types=types)
        df = vcf_to_dataframe(vcf_path, fields=fields, alt_number=2, numbers=numbers,
                              chunk_length=2, types=types)
        assert_list_equal(['CHROM', 'POS', 'REF', 'ALT_1', 'ALT_2', 'DP', 'AC_1',
                           'AC_2', 'AC_3'],
                          df.columns.tolist())
        # always convert strings to object dtype for pandas
        eq_(np.dtype(object), df['CHROM'].dtype)
        eq_(np.dtype(object), df['ALT_1'].dtype)
        check_dataframe(callset, df)


def test_vcf_to_dataframe_all():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    fields = '*'
    numbers = {'AC': 3}
    for string_type in 'S10', 'object':
        types = {'CHROM': string_type, 'ALT': string_type}
        callset = read_vcf(vcf_path, fields=fields, alt_number=2, numbers=numbers,
                           types=types)
        df = vcf_to_dataframe(vcf_path, fields=fields, alt_number=2, numbers=numbers,
                              chunk_length=2, types=types)
        for k in ['CHROM', 'POS', 'ID', 'REF', 'ALT_1', 'ALT_2', 'DP', 'AC_1',
                  'AC_2', 'AC_3']:
            assert k in df.columns.tolist()
        # always convert strings to object dtype for pandas
        eq_(np.dtype(object), df['CHROM'].dtype)
        eq_(np.dtype(object), df['ALT_1'].dtype)
        check_dataframe(callset, df)


def test_vcf_to_dataframe_exclude():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    fields = '*'
    exclude = ['ALT', 'ID']
    df = vcf_to_dataframe(vcf_path, fields=fields, exclude_fields=exclude)
    for k in ['CHROM', 'POS', 'REF', 'DP', 'AC_1', 'AC_2', 'AC_3']:
        assert k in df.columns.tolist()
    for k in ['ALT_1', 'ALT_2', 'ID']:
        assert k not in df.columns.tolist()


def test_vcf_to_dataframe_ann():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'ann.vcf')
    fields = ['CHROM', 'POS', 'REF', 'ALT', 'ANN', 'DP', 'AC', 'GT']
    numbers = {'AC': 2, 'ALT': 2}
    for string_type in 'S10', 'object':
        types = {'CHROM': string_type, 'ALT': string_type}
        transformers = [ANNTransformer(fields=['Allele', 'HGVS_c', 'AA'],
                                       types={'Allele': string_type,
                                              'HGVS_c': string_type})]
        callset = read_vcf(vcf_path, fields=fields, numbers=numbers, types=types,
                           transformers=transformers)
        df = vcf_to_dataframe(vcf_path, fields=fields, numbers=numbers, chunk_length=2,
                              types=types, transformers=transformers)
        assert_list_equal(['CHROM', 'POS', 'REF', 'ALT_1', 'ALT_2', 'ANN_Allele',
                           'ANN_HGVS_c', 'ANN_AA_pos', 'ANN_AA_length', 'DP', 'AC_1',
                           'AC_2'],
                          df.columns.tolist())
        # always convert strings to object dtype for pandas
        eq_(np.dtype(object), df['CHROM'].dtype)
        eq_(np.dtype(object), df['ALT_1'].dtype)
        check_dataframe(callset, df)


def test_vcf_to_csv():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    fields = ['CHROM', 'POS', 'REF', 'ALT', 'DP', 'AC', 'GT']
    numbers = {'AC': 3}
    for string_type in 'S20', 'object':
        types = {'REF': string_type, 'ALT': string_type}
        df = vcf_to_dataframe(vcf_path, fields=fields, alt_number=2, numbers=numbers,
                              types=types, chunk_length=2)
        csv_path = os.path.join(tempdir, 'test.csv')
        if os.path.exists(csv_path):
            os.remove(csv_path)
        vcf_to_csv(vcf_path, csv_path, fields=fields, alt_number=2, numbers=numbers,
                   types=types, chunk_length=2)
        import pandas
        adf = pandas.read_csv(csv_path, na_filter=True)
        assert_list_equal(df.columns.tolist(), adf.columns.tolist())
        for k in df.columns:
            compare_arrays(df[k].values, adf[k].values)


def test_vcf_to_csv_all():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    fields = '*'
    df = vcf_to_dataframe(vcf_path, fields=fields)
    csv_path = os.path.join(tempdir, 'test.csv')
    if os.path.exists(csv_path):
        os.remove(csv_path)
    vcf_to_csv(vcf_path, csv_path, fields=fields)
    import pandas
    adf = pandas.read_csv(csv_path, na_filter=True)
    assert_list_equal(df.columns.tolist(), adf.columns.tolist())
    for k in df.columns:
        compare_arrays(df[k].values, adf[k].values)


def test_vcf_to_csv_exclude():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    fields = '*'
    exclude = ['ALT', 'ID']
    df = vcf_to_dataframe(vcf_path, fields=fields, exclude_fields=exclude)
    csv_path = os.path.join(tempdir, 'test.csv')
    if os.path.exists(csv_path):
        os.remove(csv_path)
    vcf_to_csv(vcf_path, csv_path, fields=fields, exclude_fields=exclude)
    import pandas
    adf = pandas.read_csv(csv_path, na_filter=True)
    assert_list_equal(df.columns.tolist(), adf.columns.tolist())


def test_vcf_to_csv_ann():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'ann.vcf')
    fields = ['CHROM', 'POS', 'REF', 'ALT', 'DP', 'AC', 'ANN', 'GT']
    numbers = {'AC': 2, 'ALT': 2}
    for string_type in 'S20', 'object':
        types = {'CHROM': string_type, 'REF': string_type, 'ALT': string_type}
        transformers = [ANNTransformer(fields=['Allele', 'HGVS_c', 'AA'],
                                       types={'Allele': string_type,
                                              'HGVS_c': string_type})]
        df = vcf_to_dataframe(vcf_path, fields=fields, numbers=numbers, types=types,
                              chunk_length=2, transformers=transformers)
        csv_path = os.path.join(tempdir, 'test.csv')
        if os.path.exists(csv_path):
            os.remove(csv_path)
        vcf_to_csv(vcf_path, csv_path, fields=fields, numbers=numbers, types=types,
                   chunk_length=2, transformers=transformers)
        import pandas
        adf = pandas.read_csv(csv_path, na_filter=True)
        assert_list_equal(df.columns.tolist(), adf.columns.tolist())
        for k in df.columns:
            compare_arrays(df[k].values, adf[k].values)


def test_vcf_to_recarray():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    fields = ['CHROM', 'POS', 'REF', 'ALT', 'DP', 'AC', 'GT']
    numbers = {'AC': 3}
    for string_type in 'S20', 'object':
        types = {'CHROM': string_type, 'REF': string_type, 'ALT': string_type}
        callset = read_vcf(vcf_path, fields=fields, alt_number=2, numbers=numbers,
                           types=types)
        a = vcf_to_recarray(vcf_path, fields=fields, alt_number=2, numbers=numbers,
                            chunk_length=2, types=types)
        assert_list_equal(['CHROM', 'POS', 'REF', 'ALT_1', 'ALT_2', 'DP', 'AC_1', 'AC_2',
                           'AC_3'], list(a.dtype.names))
        eq_(np.dtype(string_type), a['CHROM'].dtype)
        for k in callset:
            if k.startswith('variants/'):
                group, name = k.split('/')
                e = callset[k]
                if e.ndim == 1:
                    assert_array_equal(e, a[name])
                elif e.ndim == 2:
                    for i in range(e.shape[1]):
                        assert_array_equal(e[:, i], a['%s_%s' % (name, i + 1)])
                else:
                    assert False, (k, e.ndim)


def test_vcf_to_recarray_all():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    fields = '*'
    numbers = {'AC': 3}
    for string_type in 'S20', 'object':
        types = {'CHROM': string_type, 'REF': string_type, 'ALT': string_type}
        callset = read_vcf(vcf_path, fields=fields, alt_number=2, numbers=numbers,
                           types=types)
        a = vcf_to_recarray(vcf_path, fields=fields, alt_number=2, numbers=numbers,
                            chunk_length=2, types=types)
        for k in ['CHROM', 'POS', 'ID', 'REF', 'ALT_1', 'ALT_2', 'DP', 'AC_1',
                  'AC_2', 'AC_3']:
            assert k in a.dtype.names
        eq_(np.dtype(string_type), a['CHROM'].dtype)
        for k in callset:
            if k.startswith('variants/'):
                group, name = k.split('/')
                e = callset[k]
                if e.ndim == 1:
                    assert_array_equal(e, a[name])
                elif e.ndim == 2:
                    for i in range(e.shape[1]):
                        assert_array_equal(e[:, i], a['%s_%s' % (name, i + 1)])
                else:
                    assert False, (k, e.ndim)


def test_vcf_to_recarray_exclude():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    fields = '*'
    exclude = ['ALT', 'ID']
    a = vcf_to_recarray(vcf_path, fields=fields, exclude_fields=exclude)
    for k in ['CHROM', 'POS', 'REF', 'DP', 'AC_1', 'AC_2', 'AC_3']:
        assert k in a.dtype.names
    for k in 'ALT_1', 'ALT_2', 'ALT', 'ID':
        assert k not in a.dtype.names


def test_vcf_to_recarray_ann():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'ann.vcf')
    fields = ['CHROM', 'POS', 'REF', 'ALT', 'ANN', 'DP', 'AC', 'GT']
    numbers = {'AC': 2, 'ALT': 2}
    for string_type in 'S20', 'object':
        types = {'CHROM': string_type, 'REF': string_type, 'ALT': string_type}
        transformers = [ANNTransformer(fields=['Allele', 'HGVS_c', 'AA'],
                                       types={'Allele': string_type,
                                              'HGVS_c': string_type})]
        callset = read_vcf(vcf_path, fields=fields, numbers=numbers, types=types,
                           transformers=transformers)
        a = vcf_to_recarray(vcf_path, fields=fields, numbers=numbers, chunk_length=2,
                            types=types, transformers=transformers)
        assert_list_equal(['CHROM', 'POS', 'REF', 'ALT_1', 'ALT_2', 'ANN_Allele',
                           'ANN_HGVS_c', 'ANN_AA_pos', 'ANN_AA_length', 'DP', 'AC_1',
                           'AC_2'],
                          list(a.dtype.names))
        eq_(np.dtype(string_type), a['CHROM'].dtype)
        eq_(np.dtype(string_type), a['ALT_1'].dtype)
        for k in callset:
            group, name = k.split('/')
            if group == 'variants':
                e = callset[k]
                if e.ndim == 1:
                    assert_array_equal(e, a[name])
                elif e.ndim == 2:
                    for i in range(e.shape[1]):
                        assert_array_equal(e[:, i], a['%s_%s' % (name, i + 1)])
                else:
                    assert False, (k, e.ndim)
            else:
                assert name not in a.dtype.names


def test_read_vcf_headers():
    vcf_path = os.path.join(os.path.dirname(__file__), 'data', 'sample.vcf')
    headers = read_vcf_headers(vcf_path)

    # check headers
    assert_in('q10', headers.filters)
    assert_in('s50', headers.filters)
    assert_in('AA', headers.infos)
    assert_in('AC', headers.infos)
    assert_in('AF', headers.infos)
    assert_in('AN', headers.infos)
    assert_in('DB', headers.infos)
    assert_in('DP', headers.infos)
    assert_in('H2', headers.infos)
    assert_in('NS', headers.infos)
    assert_in('DP', headers.formats)
    assert_in('GQ', headers.formats)
    assert_in('GT', headers.formats)
    assert_in('HQ', headers.formats)
    eq_(['NA00001', 'NA00002', 'NA00003'], headers.samples)
    eq_('1', headers.infos['AA']['Number'])
    eq_('String', headers.infos['AA']['Type'])
    eq_('Ancestral Allele', headers.infos['AA']['Description'])
    eq_('2', headers.formats['HQ']['Number'])
    eq_('Integer', headers.formats['HQ']['Type'])
    eq_('Haplotype Quality', headers.formats['HQ']['Description'])
