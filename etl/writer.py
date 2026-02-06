def write_finance(conn, df, tenant_id):
    df["tenant_id"] = tenant_id
    df.to_sql("indicadores_financeiros", conn, if_exists="append", index=False)

def write_sales(conn, df, tenant_id):
    df["tenant_id"] = tenant_id
    df.to_sql("indicadores_vendas", conn, if_exists="append", index=False)

def write_ops(conn, df, tenant_id):
    df["tenant_id"] = tenant_id
    df.to_sql("indicadores_operacionais", conn, if_exists="append", index=False)

def write_marketing(conn, df, tenant_id):
    df["tenant_id"] = tenant_id
    df.to_sql("indicadores_marketing", conn, if_exists="append", index=False)

def write_clients(conn, df, tenant_id):
    df["tenant_id"] = tenant_id
    df.to_sql("indicadores_clientes", conn, if_exists="append", index=False)