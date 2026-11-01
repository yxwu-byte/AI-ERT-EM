import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import COLUMNS,load_csv
from survey_io import ImportOptions,table,suggest_mapping,convert_table,read_bert,read_res2dinv_wenner,write_csv

SAMPLES=Path(__file__).resolve().parents[1]/'examples'

class ConversionTests(unittest.TestCase):
    def assert_same(self,rows):
        expected=load_csv(SAMPLES/'conductive_block.csv')
        self.assertEqual(len(rows),len(expected))
        for actual,reference in zip(rows,expected):
            for key in COLUMNS:self.assertAlmostEqual(actual[key],reference[key],places=9)

    def test_equivalent_resistance_percent(self):
        path=SAMPLES/'resistance_percent.tsv'
        rows,report=convert_table(path,suggest_mapping(table(path)[0]),ImportOptions(value_mode='resistance',error_percent=True))
        self.assert_same(rows);self.assertFalse(report['estimated_errors'])

    def test_equivalent_voltage_milliamps(self):
        path=SAMPLES/'voltage_current.csv'
        rows,_=convert_table(path,suggest_mapping(table(path)[0]),ImportOptions(value_mode='voltage_current',voltage_scale=.001,current_scale=.001,error_percent=True))
        self.assert_same(rows)

    def test_indexed_electrode_table(self):
        path=SAMPLES/'electrode_ids.csv'
        rows,_=convert_table(path,suggest_mapping(table(path)[0]),ImportOptions(coordinate_mode='indices',electrode_file=str(SAMPLES/'electrodes.csv')))
        self.assert_same(rows)
        with self.assertRaises(ValueError):convert_table(path,suggest_mapping(table(path)[0]),ImportOptions(coordinate_mode='indices'))

    def test_native_formats(self):
        self.assert_same(read_bert(SAMPLES/'conductive_block.ohm')[0])
        rows,report=read_res2dinv_wenner(SAMPLES/'wenner_res2dinv.dat')
        self.assert_same(rows);self.assertTrue(report['estimated_errors'])

    def test_position_units_default_errors_and_export(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.csv'
            path.write_text('a,b,m,n,rhoa\n0,300,100,200,100\n')
            rows,report=convert_table(path,suggest_mapping(table(path)[0]),ImportOptions(position_scale=.01,default_error=.05))
            self.assertEqual(rows[0]['bx'],3);self.assertEqual(rows[0]['error'],.05)
            self.assertTrue(report['estimated_errors'])
            out=Path(folder)/'converted.csv';write_csv(out,rows);self.assertEqual(load_csv(out),rows)

    def test_invalid_scientific_conversion(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.csv'
            for contents in ['ax,bx,mx,nx,u,i\n0,3,1,2,1,0\n','ax,bx,mx,nx,u,i\n0,3,1,2,nan,1\n']:
                path.write_text(contents)
                with self.assertRaises(ValueError):convert_table(path,suggest_mapping(table(path)[0]),ImportOptions(value_mode='voltage_current'))
            native=Path(folder)/'topography.ohm'
            native.write_text((SAMPLES/'conductive_block.ohm').read_text().replace('0\t0\t0','0\t0\t1',1))
            with self.assertRaises(ValueError):read_bert(native)

if __name__=='__main__':unittest.main()
