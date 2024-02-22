import csv
import json

org_tree = {'campuses': {}}
with open('./umn_org_tree.csv', mode='r') as file:
    reader = csv.DictReader(file)
    for row in reader:
        campus = row['UM_CAMPUS_DESCR'] 
        if campus not in org_tree['campuses']:
            org_tree['campuses'][campus] = {'campus_id': row['UM_CAMPUS'], 'vps': {}}

        vp = row['UM_VP_DESCR'] 
        if vp not in org_tree['campuses'][campus]['vps']:
            org_tree['campuses'][campus]['vps'][vp] = {'vp_id': row['UM_VP'], 'colleges': {}}

        college = row['UM_COLLEGE_DESCR'] 
        if college not in org_tree['campuses'][campus]['vps'][vp]['colleges']:
            org_tree['campuses'][campus]['vps'][vp]['colleges'][college] = {'college_id': row['UM_COLLEGE'], 'zdepts': {}}

        zdept = row['UM_ZDEPTID_DESCR'] 
        if zdept not in org_tree['campuses'][campus]['vps'][vp]['colleges'][college]['zdepts']:
            org_tree['campuses'][campus]['vps'][vp]['colleges'][college]['zdepts'][zdept] = {'zdept_id': row['UM_ZDEPTID'], 'depts': {}}

        dept = row['DESCR'] 
        if dept not in org_tree['campuses'][campus]['vps'][vp]['colleges'][college]['zdepts'][zdept]['depts']:
            org_tree['campuses'][campus]['vps'][vp]['colleges'][college]['zdepts'][zdept]['depts'][dept] = {'dept_id': row['DEPTID']}

print(json.dumps(org_tree, sort_keys=True, indent=4))
