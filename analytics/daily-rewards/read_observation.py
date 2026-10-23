"""Read existing server records through the configured Gifgloo SSH connection."""
import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort-start', required=True)
    parser.add_argument('--cohort-end', required=True)
    parser.add_argument('--observed-until', required=True)
    parser.add_argument('--internal-account-ids', default='')
    args = parser.parse_args()
    params = vars(args)
    dates = [datetime.fromisoformat(params[key].replace('Z', '+00:00'))
             for key in ('cohort_start', 'cohort_end', 'observed_until')]
    if any(date.tzinfo is None for date in dates) or not dates[0] < dates[1] <= dates[2]:
        parser.error('Use timezone-aware timestamps with start < end <= observed-until.')
    if any(not account.replace('-', '').isalnum() for account in args.internal_account_ids.split(',') if account):
        parser.error('Internal account IDs must be identifiers.')
    queries = {}
    for name, filename in [('daily_reward', 'report.sql'), ('payment', 'payments.sql')]:
        sql = Path(__file__).with_name(filename).read_text()
        sql = sql.split('WITH ', 1)[-1] if name == 'daily_reward' else sql.split('SELECT ', 1)[-1]
        sql = ('WITH ' if name == 'daily_reward' else 'SELECT ') + sql.split(';')[0]
        queries[name] = re.sub(r":'([a-z_]+)'::timestamptz", r'CAST(:\1 AS timestamptz)', sql)
        queries[name] = re.sub(r":'([a-z_]+)'", r':\1', queries[name])
    program = '''import json, os
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
params = PARAMS
queries = QUERIES
with create_engine(os.environ['DATABASE_URL']).connect() as c:
    c.execute(text('SET TRANSACTION READ ONLY'))
    c.execute(text("SET LOCAL statement_timeout = '15s'"))
    rewards = [dict(row._mapping) for row in c.execute(text(queries['daily_reward']), params)]
    payments = [dict(row._mapping) for row in c.execute(text(queries['payment']), params)]
    summary = {'survey_accounts': len(rewards), 'claim_accounts': sum(row['claim_days'] > 0 for row in rewards)}
    for key in ('claim_days', 'granted_uses', 'deducted_daily_jobs', 'refunded_daily_jobs', 'completed_daily_jobs', 'failed_daily_jobs', 'completed_jobs_after_first_claim'):
        summary[key] = sum(row[key] for row in rewards)
    result = {'cohort_start': params['cohort_start'], 'cohort_end': params['cohort_end'],
        'observed_until': params['observed_until'], 'queried_at': datetime.now(timezone.utc).isoformat(),
        'excluded_account_count': len([a for a in params['internal_account_ids'].split(',') if a]),
        'daily_reward': summary, 'payments': payments,
        'status_basis': 'Current job/payment status; timestamps limit submissions, requests and ledger entries. Not a historical status reconstruction.'}
    c.rollback()
print(json.dumps(result, default=str, ensure_ascii=False))
'''.replace('PARAMS', repr(params)).replace('QUERIES', repr(queries))
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', 'gifgloo',
                             'docker', 'exec', '-i', 'gifgloo-backend', 'python', '-'],
                            input=program, text=True, capture_output=True, check=True, timeout=60)
    print(json.dumps(json.loads(result.stdout), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
