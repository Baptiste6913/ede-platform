pg_dump: warning: there are circular foreign-key constraints on this table:
pg_dump: detail: hypertable
pg_dump: hint: You might not be able to restore the dump without using --disable-triggers or temporarily dropping the constraints.
pg_dump: hint: Consider using a full dump instead of a --data-only dump to avoid this problem.
pg_dump: warning: there are circular foreign-key constraints on this table:
pg_dump: detail: chunk
pg_dump: hint: You might not be able to restore the dump without using --disable-triggers or temporarily dropping the constraints.
pg_dump: hint: Consider using a full dump instead of a --data-only dump to avoid this problem.
pg_dump: warning: there are circular foreign-key constraints on this table:
pg_dump: detail: continuous_agg
pg_dump: hint: You might not be able to restore the dump without using --disable-triggers or temporarily dropping the constraints.
pg_dump: hint: Consider using a full dump instead of a --data-only dump to avoid this problem.
--
-- PostgreSQL database dump
--

\restrict 4InCuFbmZ3iI4RcodlPnKBnkjNMdgpXgJGWfYPJ2bJfafL5bfRVhAP6k8I6WCYC

-- Dumped from database version 16.13 (Ubuntu 16.13-1.pgdg22.04+1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-1.pgdg22.04+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: timescaledb; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS timescaledb WITH SCHEMA public;


--
-- Name: EXTENSION timescaledb; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION timescaledb IS 'Enables scalable inserts and complex queries for time-series data (Community Edition)';


--
-- Name: timescaledb_toolkit; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS timescaledb_toolkit WITH SCHEMA public;


--
-- Name: EXTENSION timescaledb_toolkit; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION timescaledb_toolkit IS 'Library of analytical hyperfunctions, time-series pipelining, and other SQL utilities';


--
-- Name: analyst_source_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.analyst_source_enum AS ENUM (
    'claude_opus_4_7',
    'manual'
);


--
-- Name: analyst_verdict_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.analyst_verdict_enum AS ENUM (
    'GO',
    'WAIT',
    'SKIP'
);


--
-- Name: currency_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.currency_enum AS ENUM (
    'EUR',
    'CHF',
    'GBP',
    'USD'
);


--
-- Name: deal_status_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.deal_status_enum AS ENUM (
    'announced',
    'cleared',
    'open',
    'closed',
    'lapsed',
    'withdrawn'
);


--
-- Name: deal_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.deal_type_enum AS ENUM (
    'opa',
    'opa_simplifiee',
    'opa_obligatoire',
    'opa_volontaire_totalitaria',
    'opa_volontaire_parziale',
    'opa_consolidamento',
    'ope',
    'opas',
    'opra',
    'opr',
    'opr_ro',
    'garantie_de_cours',
    'pflichtangebot',
    'freiwilliges_uebernahmeangebot',
    'delisting_erwerbsangebot',
    'erwerbsangebot'
);


--
-- Name: decision_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.decision_enum AS ENUM (
    'enter',
    'wait',
    'skip'
);


--
-- Name: event_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.event_type_enum AS ENUM (
    'filing_amf',
    'filing_consob',
    'filing_bafin',
    'clearance',
    'extension',
    'waiver',
    'MAC',
    'court_ruling',
    'antitrust_decision',
    'FDI_decision',
    'FSR_decision',
    'news',
    'price_update',
    'shareholder_disclosure'
);


--
-- Name: jurisdiction_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.jurisdiction_enum AS ENUM (
    'FR',
    'IT',
    'DE'
);


--
-- Name: position_side_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.position_side_enum AS ENUM (
    'long',
    'short'
);


--
-- Name: position_status_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.position_status_enum AS ENUM (
    'open',
    'closed',
    'stopped'
);


--
-- Name: price_source_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.price_source_enum AS ENUM (
    'ibkr',
    'stooq'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: prices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prices (
    ticker character varying(32) NOT NULL,
    ts timestamp with time zone NOT NULL,
    open numeric(18,6) NOT NULL,
    high numeric(18,6) NOT NULL,
    low numeric(18,6) NOT NULL,
    close numeric(18,6) NOT NULL,
    volume bigint,
    source public.price_source_enum NOT NULL
);


--
-- Name: _direct_view_2; Type: VIEW; Schema: _timescaledb_internal; Owner: -
--

CREATE VIEW _timescaledb_internal._direct_view_2 AS
 SELECT ticker,
    public.time_bucket('01:00:00'::interval, ts) AS bucket,
    public.first(open, ts) AS open,
    max(high) AS high,
    min(low) AS low,
    public.last(close, ts) AS close,
    sum(volume) AS volume
   FROM public.prices
  GROUP BY ticker, (public.time_bucket('01:00:00'::interval, ts));


--
-- Name: _direct_view_3; Type: VIEW; Schema: _timescaledb_internal; Owner: -
--

CREATE VIEW _timescaledb_internal._direct_view_3 AS
 SELECT ticker,
    public.time_bucket('1 day'::interval, ts) AS bucket,
    public.first(open, ts) AS open,
    max(high) AS high,
    min(low) AS low,
    public.last(close, ts) AS close,
    sum(volume) AS volume
   FROM public.prices
  GROUP BY ticker, (public.time_bucket('1 day'::interval, ts));


--
-- Name: _materialized_hypertable_2; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._materialized_hypertable_2 (
    ticker character varying(32),
    bucket timestamp with time zone NOT NULL,
    open numeric,
    high numeric,
    low numeric,
    close numeric,
    volume numeric
);


--
-- Name: _materialized_hypertable_3; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._materialized_hypertable_3 (
    ticker character varying(32),
    bucket timestamp with time zone NOT NULL,
    open numeric,
    high numeric,
    low numeric,
    close numeric,
    volume numeric
);


--
-- Name: _partial_view_2; Type: VIEW; Schema: _timescaledb_internal; Owner: -
--

CREATE VIEW _timescaledb_internal._partial_view_2 AS
 SELECT ticker,
    public.time_bucket('01:00:00'::interval, ts) AS bucket,
    public.first(open, ts) AS open,
    max(high) AS high,
    min(low) AS low,
    public.last(close, ts) AS close,
    sum(volume) AS volume
   FROM public.prices
  GROUP BY ticker, (public.time_bucket('01:00:00'::interval, ts));


--
-- Name: _partial_view_3; Type: VIEW; Schema: _timescaledb_internal; Owner: -
--

CREATE VIEW _timescaledb_internal._partial_view_3 AS
 SELECT ticker,
    public.time_bucket('1 day'::interval, ts) AS bucket,
    public.first(open, ts) AS open,
    max(high) AS high,
    min(low) AS low,
    public.last(close, ts) AS close,
    sum(volume) AS volume
   FROM public.prices
  GROUP BY ticker, (public.time_bucket('1 day'::interval, ts));


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: analyses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.analyses (
    id integer NOT NULL,
    deal_id integer NOT NULL,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    source public.analyst_source_enum NOT NULL,
    brief_path text,
    verdict public.analyst_verdict_enum NOT NULL,
    thesis_md text,
    risks jsonb,
    catalysts jsonb
);


--
-- Name: analyses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.analyses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: analyses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.analyses_id_seq OWNED BY public.analyses.id;


--
-- Name: deals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.deals (
    id integer NOT NULL,
    juridiction public.jurisdiction_enum NOT NULL,
    regulator_ref character varying(128) NOT NULL,
    ticker_target character varying(32),
    ticker_acquirer character varying(32),
    target_name character varying(255) NOT NULL,
    acquirer_name character varying(255) NOT NULL,
    announcement_date date NOT NULL,
    deal_type public.deal_type_enum NOT NULL,
    status public.deal_status_enum NOT NULL,
    offer_price numeric(18,6),
    currency public.currency_enum,
    payment_cash_share numeric(5,4),
    premium_pct numeric(7,4),
    min_acceptance_threshold numeric(5,4),
    expected_close_date date,
    source_url text,
    pdf_path text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    secondary_jurisdictions public.jurisdiction_enum[]
);


--
-- Name: deals_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.deals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: deals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.deals_id_seq OWNED BY public.deals.id;


--
-- Name: events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.events (
    id integer NOT NULL,
    deal_id integer NOT NULL,
    ts timestamp with time zone NOT NULL,
    event_type public.event_type_enum NOT NULL,
    description text,
    source_url text,
    raw_payload jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.events_id_seq OWNED BY public.events.id;


--
-- Name: paper_positions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.paper_positions (
    id integer NOT NULL,
    deal_id integer NOT NULL,
    open_ts timestamp with time zone DEFAULT now() NOT NULL,
    close_ts timestamp with time zone,
    entry_price numeric(18,6) NOT NULL,
    exit_price numeric(18,6),
    size_eur numeric(14,2) NOT NULL,
    side public.position_side_enum NOT NULL,
    pnl_eur numeric(14,2),
    status public.position_status_enum NOT NULL,
    notes text,
    CONSTRAINT ck_paper_positions_size_eur_positive CHECK ((size_eur > (0)::numeric))
);


--
-- Name: paper_positions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.paper_positions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: paper_positions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.paper_positions_id_seq OWNED BY public.paper_positions.id;


--
-- Name: prices_1d; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.prices_1d AS
 SELECT ticker,
    bucket,
    open,
    high,
    low,
    close,
    volume
   FROM _timescaledb_internal._materialized_hypertable_3;


--
-- Name: prices_1h; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.prices_1h AS
 SELECT ticker,
    bucket,
    open,
    high,
    low,
    close,
    volume
   FROM _timescaledb_internal._materialized_hypertable_2;


--
-- Name: scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scores (
    id integer NOT NULL,
    deal_id integer NOT NULL,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    p_completion numeric(6,5) NOT NULL,
    p_market_implied numeric(6,5),
    edge numeric(7,5),
    expected_return_annualized numeric(8,5),
    decision public.decision_enum NOT NULL,
    model_version character varying(64) NOT NULL,
    features jsonb,
    CONSTRAINT ck_scores_p_completion CHECK (((p_completion >= (0)::numeric) AND (p_completion <= (1)::numeric))),
    CONSTRAINT ck_scores_p_market_implied CHECK (((p_market_implied IS NULL) OR ((p_market_implied >= (0)::numeric) AND (p_market_implied <= (1)::numeric))))
);


--
-- Name: scores_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.scores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: scores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.scores_id_seq OWNED BY public.scores.id;


--
-- Name: analyses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analyses ALTER COLUMN id SET DEFAULT nextval('public.analyses_id_seq'::regclass);


--
-- Name: deals id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deals ALTER COLUMN id SET DEFAULT nextval('public.deals_id_seq'::regclass);


--
-- Name: events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events ALTER COLUMN id SET DEFAULT nextval('public.events_id_seq'::regclass);


--
-- Name: paper_positions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_positions ALTER COLUMN id SET DEFAULT nextval('public.paper_positions_id_seq'::regclass);


--
-- Name: scores id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scores ALTER COLUMN id SET DEFAULT nextval('public.scores_id_seq'::regclass);


--
-- Data for Name: hypertable; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.hypertable (id, schema_name, table_name, associated_schema_name, associated_table_prefix, num_dimensions, chunk_sizing_func_schema, chunk_sizing_func_name, chunk_target_size, compression_state, compressed_hypertable_id, status) FROM stdin;
1	public	prices	_timescaledb_internal	_hyper_1	1	_timescaledb_functions	calculate_chunk_interval	0	0	\N	0
2	_timescaledb_internal	_materialized_hypertable_2	_timescaledb_internal	_hyper_2	1	_timescaledb_functions	calculate_chunk_interval	0	0	\N	0
3	_timescaledb_internal	_materialized_hypertable_3	_timescaledb_internal	_hyper_3	1	_timescaledb_functions	calculate_chunk_interval	0	0	\N	0
\.


--
-- Data for Name: bgw_job; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.bgw_job (id, application_name, schedule_interval, max_runtime, max_retries, retry_period, proc_schema, proc_name, owner, scheduled, fixed_schedule, initial_start, hypertable_id, config, check_schema, check_name, timezone) FROM stdin;
1000	Refresh Continuous Aggregate Policy [1000]	00:30:00	00:00:00	-1	00:30:00	_timescaledb_functions	policy_refresh_continuous_aggregate	ede	t	f	\N	2	{"end_offset": "01:00:00", "start_offset": "2 days", "mat_hypertable_id": 2}	_timescaledb_functions	policy_refresh_continuous_aggregate_check	\N
1001	Refresh Continuous Aggregate Policy [1001]	01:00:00	00:00:00	-1	01:00:00	_timescaledb_functions	policy_refresh_continuous_aggregate	ede	t	f	\N	3	{"end_offset": "1 day", "start_offset": "7 days", "mat_hypertable_id": 3}	_timescaledb_functions	policy_refresh_continuous_aggregate_check	\N
\.


--
-- Data for Name: chunk; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.chunk (id, hypertable_id, schema_name, table_name, compressed_chunk_id, status, osm_chunk, creation_time) FROM stdin;
\.


--
-- Data for Name: chunk_column_stats; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.chunk_column_stats (id, hypertable_id, chunk_id, column_name, range_start, range_end, valid) FROM stdin;
\.


--
-- Data for Name: dimension; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.dimension (id, hypertable_id, column_name, column_type, aligned, num_slices, partitioning_func_schema, partitioning_func, interval_length, compress_interval_length, integer_now_func_schema, integer_now_func) FROM stdin;
1	1	ts	timestamp with time zone	t	\N	\N	\N	604800000000	\N	\N	\N
2	2	bucket	timestamp with time zone	t	\N	\N	\N	6048000000000	\N	\N	\N
3	3	bucket	timestamp with time zone	t	\N	\N	\N	6048000000000	\N	\N	\N
\.


--
-- Data for Name: dimension_slice; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.dimension_slice (id, dimension_id, range_start, range_end) FROM stdin;
\.


--
-- Data for Name: chunk_constraint; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.chunk_constraint (chunk_id, dimension_slice_id, constraint_name, hypertable_constraint_name) FROM stdin;
\.


--
-- Data for Name: compression_chunk_size; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.compression_chunk_size (chunk_id, compressed_chunk_id, uncompressed_heap_size, uncompressed_toast_size, uncompressed_index_size, compressed_heap_size, compressed_toast_size, compressed_index_size, numrows_pre_compression, numrows_post_compression, numrows_frozen_immediately) FROM stdin;
\.


--
-- Data for Name: compression_settings; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.compression_settings (relid, compress_relid, segmentby, orderby, orderby_desc, orderby_nullsfirst, index) FROM stdin;
\.


--
-- Data for Name: continuous_agg; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.continuous_agg (mat_hypertable_id, raw_hypertable_id, parent_mat_hypertable_id, user_view_schema, user_view_name, partial_view_schema, partial_view_name, direct_view_schema, direct_view_name, materialized_only) FROM stdin;
2	1	\N	public	prices_1h	_timescaledb_internal	_partial_view_2	_timescaledb_internal	_direct_view_2	t
3	1	\N	public	prices_1d	_timescaledb_internal	_partial_view_3	_timescaledb_internal	_direct_view_3	t
\.


--
-- Data for Name: continuous_aggs_bucket_function; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.continuous_aggs_bucket_function (mat_hypertable_id, bucket_func, bucket_width, bucket_origin, bucket_offset, bucket_timezone, bucket_fixed_width) FROM stdin;
2	public.time_bucket(interval,timestamp with time zone)	01:00:00	\N	\N	\N	t
3	public.time_bucket(interval,timestamp with time zone)	1 day	\N	\N	\N	t
\.


--
-- Data for Name: continuous_aggs_hypertable_invalidation_log; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.continuous_aggs_hypertable_invalidation_log (hypertable_id, lowest_modified_value, greatest_modified_value) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_invalidation_threshold; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.continuous_aggs_invalidation_threshold (hypertable_id, watermark) FROM stdin;
1	1778706000000000
\.


--
-- Data for Name: continuous_aggs_jobs_refresh_ranges; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.continuous_aggs_jobs_refresh_ranges (materialization_id, start_range, end_range, pid, job_id, created_at) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_materialization_invalidation_log; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.continuous_aggs_materialization_invalidation_log (materialization_id, lowest_modified_value, greatest_modified_value) FROM stdin;
2	-9223372036854775808	1778529599999999
3	-9223372036854775808	1778111999999999
3	1778544000000000	9223372036854775807
2	1778706000000000	9223372036854775807
\.


--
-- Data for Name: continuous_aggs_materialization_ranges; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.continuous_aggs_materialization_ranges (materialization_id, lowest_modified_value, greatest_modified_value) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_watermark; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.continuous_aggs_watermark (mat_hypertable_id, watermark) FROM stdin;
2	-210866803200000000
3	-210866803200000000
\.


--
-- Data for Name: metadata; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.metadata (key, value, include_in_telemetry) FROM stdin;
install_timestamp	2026-05-12 13:05:27.441172+00	t
timescaledb_version	2.26.4	f
exported_uuid	47320a26-a07f-4939-a5b0-5aa46f99bd10	t
\.


--
-- Data for Name: tablespace; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: -
--

COPY _timescaledb_catalog.tablespace (id, hypertable_id, tablespace_name) FROM stdin;
\.


--
-- Data for Name: _materialized_hypertable_2; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: -
--

COPY _timescaledb_internal._materialized_hypertable_2 (ticker, bucket, open, high, low, close, volume) FROM stdin;
\.


--
-- Data for Name: _materialized_hypertable_3; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: -
--

COPY _timescaledb_internal._materialized_hypertable_3 (ticker, bucket, open, high, low, close, volume) FROM stdin;
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
0004
\.


--
-- Data for Name: analyses; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.analyses (id, deal_id, ts, source, brief_path, verdict, thesis_md, risks, catalysts) FROM stdin;
\.


--
-- Data for Name: deals; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.deals (id, juridiction, regulator_ref, ticker_target, ticker_acquirer, target_name, acquirer_name, announcement_date, deal_type, status, offer_price, currency, payment_cash_share, premium_pct, min_acceptance_threshold, expected_close_date, source_url, pdf_path, created_at, updated_at, secondary_jurisdictions) FROM stdin;
1	FR	226C0661	\N	\N	MEDIA 6	[pending parse]	2026-05-11	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0661/954781AD2F1F1BF3816AA9C708025BF72D9C54D8CFCF908238AD85B40E413D3B.pdf	/repo/data/pdfs/fr/2026/226C0661.pdf	2026-05-13 19:17:18.077984+00	2026-05-13 19:17:18.077984+00	\N
2	FR	226C0645	\N	\N	MEDIA 6	[pending parse]	2026-05-07	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0645/FE0616923D43D1F060E72056AFCF74F91E1A385883F3C547318A36E8027D6E2E.pdf	/repo/data/pdfs/fr/2026/226C0645.pdf	2026-05-13 19:17:19.08617+00	2026-05-13 19:17:19.08617+00	\N
3	FR	226C0644	\N	\N	FNAC DARTY	[pending parse]	2026-05-12	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0644/72DF20BE22E022A2C30DC6186B5CC3F77B31B85FA0D84EE9D1465AF96DF8A90C.pdf	/repo/data/pdfs/fr/2026/226C0644.pdf	2026-05-13 19:17:20.112296+00	2026-05-13 19:17:20.112296+00	\N
4	FR	226C0620	\N	\N	VINPAI	[pending parse]	2026-05-04	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0620/C88737C27EBA36B4ABE577D1CF942FADDF3FCB9A27BDA639FEA0105D816741C4.pdf	/repo/data/pdfs/fr/2026/226C0620.pdf	2026-05-13 19:17:21.186923+00	2026-05-13 19:17:21.186923+00	\N
5	FR	226C0591	\N	\N	ELECTRICITE ET EAUX DE MADAGASCAR	[pending parse]	2026-04-28	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0591/348695808BFBEBA6FD7244F05D2B43B6FB5C3DDBB70A75CFDDE0145335D82145.pdf	/repo/data/pdfs/fr/2026/226C0591.pdf	2026-05-13 19:17:22.233159+00	2026-05-13 19:17:22.233159+00	\N
6	FR	226C0578	\N	\N	POULAILLON	[pending parse]	2026-04-23	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0578/B956DC68725674FD12F3349D2160F0F214B32A3B47E1E2C948F36C10F05C7C1D.pdf	/repo/data/pdfs/fr/2026/226C0578.pdf	2026-05-13 19:17:23.417253+00	2026-05-13 19:17:23.417253+00	\N
7	FR	226C0550	\N	\N	TERACT	[pending parse]	2026-04-20	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0550/790CEA3A90861D7F49FCC7EC86FDEE425D31E42EEA5597D127F45DCF68783FB8.pdf	/repo/data/pdfs/fr/2026/226C0550.pdf	2026-05-13 19:17:24.506542+00	2026-05-13 19:17:24.506542+00	\N
8	FR	226C0538	\N	\N	SOCIETE DE LA TOUR EIFFEL	[pending parse]	2026-04-17	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0538/F1A0A887F62CDDB65C1D688EA3F99A87CCBF26975A738C848CFAF5EB83C3E9AB.pdf	/repo/data/pdfs/fr/2026/226C0538.pdf	2026-05-13 19:17:25.683835+00	2026-05-13 19:17:25.683835+00	\N
9	FR	226C0531	\N	\N	MEDIA 6	[pending parse]	2026-04-16	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0531/561AA4EE77DE083659474F2355A75F1A1AFA156AD34FED1FC6872CCF0A07CE87.pdf	/repo/data/pdfs/fr/2026/226C0531.pdf	2026-05-13 19:17:26.75835+00	2026-05-13 19:17:26.75835+00	\N
10	FR	226C0511	\N	\N	GAUMONT	[pending parse]	2026-04-13	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0511/AB617FF3C053B29C0869579FC6C94E567E94EF5CA54AD731BEFC90096BF14FB9.pdf	/repo/data/pdfs/fr/2026/226C0511.pdf	2026-05-13 19:17:27.859692+00	2026-05-13 19:17:27.859692+00	\N
11	FR	226C0347	\N	\N	BALYO	[pending parse]	2026-03-19	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0347/0B2F7A8AF7A42A5DB26EAA3C63A63EAEB4397FC23899488D3EE974E2276033AD.pdf	/repo/data/pdfs/fr/2026/226C0347.pdf	2026-05-13 19:17:28.911507+00	2026-05-13 19:17:28.911507+00	\N
12	FR	226C0318	\N	\N	MEDIA 6	[pending parse]	2026-03-16	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0318/2E2150D58F6F479C2C8EF560F6397E1558E9AF7DDB22A89699FC6027C7914D34.pdf	/repo/data/pdfs/fr/2026/226C0318.pdf	2026-05-13 19:17:29.86892+00	2026-05-13 19:17:29.86892+00	\N
13	FR	226C0287	\N	\N	FNAC DARTY	[pending parse]	2026-03-12	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0287/DBE2E400A000FC29A55CD25156BC15A62A7E389B563ED4E91BC02C772EA0F33F.pdf	/repo/data/pdfs/fr/2026/226C0287.pdf	2026-05-13 19:17:31.001087+00	2026-05-13 19:17:31.001087+00	\N
14	FR	226C0278	\N	\N	TERACT	[pending parse]	2026-03-09	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0278/A31DB49A0FE6CB4A382C7B960FF679D3F9018C80059A4C02ECC31EB5E653A6CE.pdf	/repo/data/pdfs/fr/2026/226C0278.pdf	2026-05-13 19:17:32.190677+00	2026-05-13 19:17:32.190677+00	\N
15	FR	226C0210	\N	\N	GROUPE TERA	[pending parse]	2026-02-19	opra	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0210/1C1F1BF8B08724AE8CC9283B6501A90015C258F03837A071E732589AE12E82E0.pdf	/repo/data/pdfs/fr/2026/226C0210.pdf	2026-05-13 19:17:33.338266+00	2026-05-13 19:17:33.338266+00	\N
16	FR	226C0157	\N	\N	TERACT	[pending parse]	2026-02-05	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0157/2954E3860C1959ADF0F7724A2D2E9CF1D89B305D888D3417CE3DF95E46E1D798.pdf	/repo/data/pdfs/fr/2026/226C0157.pdf	2026-05-13 19:17:34.507308+00	2026-05-13 19:17:34.507308+00	\N
17	FR	226C0156	\N	\N	UV GERMI	[pending parse]	2026-02-05	opra	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0156/66D132B49FB29CB455C97C16A2949728C4D3153D4E3A35EF0F7E7B5E8B9D09CD.pdf	/repo/data/pdfs/fr/2026/226C0156.pdf	2026-05-13 19:17:35.535691+00	2026-05-13 19:17:35.535691+00	\N
18	FR	226C0095	\N	\N	SOCIETE DE TAYNINH	[pending parse]	2026-01-23	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0095/69C403AC9DB64955C7CF92305B5B134E2AD8BE64C70A33B64DE758B67E616C68.pdf	/repo/data/pdfs/fr/2026/226C0095.pdf	2026-05-13 19:17:36.540198+00	2026-05-13 19:17:36.540198+00	\N
19	FR	226C0020	\N	\N	BALYO	[pending parse]	2026-01-07	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0020/DFF429DF18AF43BC18E7971ABF71A2F5B90B0255B4EBB18EB268F6D1579C2074.pdf	/repo/data/pdfs/fr/2026/226C0020.pdf	2026-05-13 19:17:37.715859+00	2026-05-13 19:17:37.715859+00	\N
20	FR	226C0008	\N	\N	GROUPE TERA	[pending parse]	2026-01-05	opra	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0008/CFFC2BF9EC93BB0D5C735AC1596CCD7BAE08ACB2F02F38BE5E387266621C223E.pdf	/repo/data/pdfs/fr/2026/226C0008.pdf	2026-05-13 19:17:38.919197+00	2026-05-13 19:17:38.919197+00	\N
21	FR	225C2156	\N	\N	PRODWARE	PHAST INVEST	2026-01-23	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2156/ADFDAA0E32B9156501354BF7041F099EE4B743B76ED64C90DE8EB363A1ABCD88.pdf	/repo/data/pdfs/fr/2026/225C2156.pdf	2026-05-13 19:17:40.102151+00	2026-05-13 19:17:40.102151+00	\N
22	FR	225C2136	\N	\N	UV GERMI	[pending parse]	2025-12-16	opra	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2136/B94BBB38882DB1DDE9148BF8D7FD9AF90D3A1681299822A01FC9104155FA4E48.pdf	/repo/data/pdfs/fr/2025/225C2136.pdf	2026-05-13 19:17:41.050517+00	2026-05-13 19:17:41.050517+00	\N
23	FR	225C2135	\N	\N	ELECTRICITE ET EAUX DE MADAGASCAR	[pending parse]	2025-12-17	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2135/5C51631DA1F169C7D81C593980694A6CCD25AE6C6A562F86302C14EDCD2F0C92.pdf	/repo/data/pdfs/fr/2025/225C2135.pdf	2026-05-13 19:17:42.094803+00	2026-05-13 19:17:42.094803+00	\N
24	FR	225C2081	\N	\N	SOCIETE DE TAYNINH	[pending parse]	2025-12-08	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2081/8CC4832C7F06C4C44A2C8A3798DA63476B655465D14B3460FE2B3DE3C7020FD0.pdf	/repo/data/pdfs/fr/2025/225C2081.pdf	2026-05-13 19:17:43.276713+00	2026-05-13 19:17:43.276713+00	\N
25	FR	225C2063	\N	\N	BALYO	[pending parse]	2026-01-22	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2063/4B74E67D96D0415272C70A7A4D4DC3BBE94E2C570A5E4BFFDAB4B0F44776363F.pdf	/repo/data/pdfs/fr/2026/225C2063.pdf	2026-05-13 19:17:44.408302+00	2026-05-13 19:17:44.408302+00	\N
26	FR	225C2061	\N	\N	COGELEC	[pending parse]	2026-01-22	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2061/1BE71CDDD093C59BF3C0816994D45C9364CA1D5E1088325B1A6E64CC57C7F564.pdf	/repo/data/pdfs/fr/2026/225C2061.pdf	2026-05-13 19:17:45.495554+00	2026-05-13 19:17:45.495554+00	\N
27	FR	225C1971	\N	\N	WAGA ENERGY	[pending parse]	2025-11-24	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1971/1561FA645F4D0517BB7B8C3D54435902C7D730202735D1145A8BF8C250D66A3C.pdf	/repo/data/pdfs/fr/2025/225C1971.pdf	2026-05-13 19:17:46.694968+00	2026-05-13 19:17:46.694968+00	\N
28	FR	225C1924	\N	\N	PRODWARE	PHAST INVEST	2025-11-14	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1924/278CEE170D11B4B719A5AF39E6EF5D5D98777BCB414E8E0447C8A4C43B17A99C.pdf	/repo/data/pdfs/fr/2025/225C1924.pdf	2026-05-13 19:17:47.602666+00	2026-05-13 19:17:47.602666+00	\N
29	FR	225C1884	\N	\N	TRONIC'S MICROSYSTEMS S.A.	TDK ELECTRONICS AG	2025-11-13	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1884/B2E25865C4580D8F7E0BAA669B6652F2AF700806DAAE34F81EBEE76DC60766A8.pdf	/repo/data/pdfs/fr/2025/225C1884.pdf	2026-05-13 19:17:48.766949+00	2026-05-13 19:17:48.766949+00	\N
30	FR	225C1797	\N	\N	PRODWARE	PHAST INVEST	2025-10-24	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1797/18E0F87ABC999B41EECECC8FE71915ACAC89A921DE6C878FBDFA509EEE420DDE.pdf	/repo/data/pdfs/fr/2025/225C1797.pdf	2026-05-13 19:17:49.895708+00	2026-05-13 19:17:49.895708+00	\N
31	FR	225C1794	\N	\N	VOGO	ABEO	2025-11-28	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1794/46A8BC8D13F4BFEE1C3F6C7EA75130F3F12717FB75CF6FF6F406DE51A430F10E.pdf	/repo/data/pdfs/fr/2025/225C1794.pdf	2026-05-13 19:17:51.100418+00	2026-05-13 19:17:51.100418+00	\N
32	FR	225C1755	\N	\N	COGELEC	[pending parse]	2025-10-15	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1755/AA36F6148357F70B3CEA5A545CC6F7C5082938EC4B57FCFF4588A719CA34AB0D.pdf	/repo/data/pdfs/fr/2025/225C1755.pdf	2026-05-13 19:17:52.328811+00	2026-05-13 19:17:52.328811+00	\N
33	FR	225C1734	\N	\N	AGROGENERATION	[pending parse]	2025-10-13	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1734/B3BE65DA8A38EFEF0C6E0B463784BE812AFE929914A3F3416AE80A2CF9A7818E.pdf	/repo/data/pdfs/fr/2025/225C1734.pdf	2026-05-13 19:17:53.333811+00	2026-05-13 19:17:53.333811+00	\N
34	FR	225C1666	\N	\N	WAGA ENERGY	[pending parse]	2025-10-02	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1666/A2460CAD381A8AA7A5E0566E2B02915BD2C21EB7F7F41119354BA67BBCF0C01E.pdf	/repo/data/pdfs/fr/2025/225C1666.pdf	2026-05-13 19:17:54.553418+00	2026-05-13 19:17:54.553418+00	\N
35	FR	225C1665	\N	\N	TRONIC'S MICROSYSTEMS S.A.	TDK ELECTRONICS AG	2025-10-01	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1665/4BCBC4A976AD1A11A4CFC01F982000092C433608C9B947BF53BA5D350947542F.pdf	/repo/data/pdfs/fr/2025/225C1665.pdf	2026-05-13 19:17:55.582848+00	2026-05-13 19:17:55.582848+00	\N
36	FR	225C1629	\N	\N	AMPLITUDE SURGICAL	[pending parse]	2025-11-28	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1629/8DF9E6C891A17EFCBB495FC63F9C7982DA9D8429C2BCBDA248C9DD77B85D97C3.pdf	/repo/data/pdfs/fr/2025/225C1629.pdf	2026-05-13 19:17:56.760958+00	2026-05-13 19:17:56.760958+00	\N
37	FR	225C1529	\N	\N	ALTAMIR	AMBOISE SAS	2025-11-28	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1529/B5E5B14DB09B63248AD314DE0677266181D86CE9711A330BBDDE64135A76DED8.pdf	/repo/data/pdfs/fr/2025/225C1529.pdf	2026-05-13 19:17:57.769374+00	2026-05-13 19:17:57.769374+00	\N
38	FR	225C1507	\N	\N	TRONIC'S MICROSYSTEMS S.A.	TDK ELECTRONICS AG	2025-09-09	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1507/E301EE3EF6B37DFAD4272EF1E160CA1E5832EADBF8D9B6387733A97822810066.pdf	/repo/data/pdfs/fr/2025/225C1507.pdf	2026-05-13 19:17:58.85417+00	2026-05-13 19:17:58.85417+00	\N
39	FR	225C1439	\N	\N	AGROGENERATION	[pending parse]	2025-08-26	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1439/24F7E7C9EB30188B5FD0914078F16AB748E20D5EE7649132863B135FE4017D31.pdf	/repo/data/pdfs/fr/2025/225C1439.pdf	2026-05-13 19:17:59.94233+00	2026-05-13 19:17:59.94233+00	\N
40	FR	225C1404	\N	\N	AGROGENERATION	[pending parse]	2025-08-18	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1404/E8EEC4E35E2DEFE94F731224C1A87EB6BB09862E30C84AA012002CD5C640C19B.pdf	/repo/data/pdfs/fr/2025/225C1404.pdf	2026-05-13 19:18:01.124906+00	2026-05-13 19:18:01.124906+00	\N
41	FR	225C1285	\N	\N	AMPLITUDE SURGICAL	[pending parse]	2025-07-30	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1285/AC0DAB36744D4ABF9AB5BE55149059EBF6F4932616FDD31223CFA13D250D0E81.pdf	/repo/data/pdfs/fr/2025/225C1285.pdf	2026-05-13 19:18:02.199776+00	2026-05-13 19:18:02.199776+00	\N
42	FR	225C1258	\N	\N	VOGO	ABEO	2025-11-28	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1258/66D00BC0E7AD03BD0F4A7BA4651F295DA8870150DFAB9075D707785B11973CF9.pdf	/repo/data/pdfs/fr/2025/225C1258.pdf	2026-05-13 19:18:03.177981+00	2026-05-13 19:18:03.177981+00	\N
43	FR	225C1227	\N	\N	GROUPE ETPO SA	GROUPE SPIE BATIGNOLLES SAS	2025-07-18	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1227/8E52F125753476B79E285A529935605690E7CDC62F9935FF2126E850B7197FCA.pdf	/repo/data/pdfs/fr/2025/225C1227.pdf	2026-05-13 19:18:04.390819+00	2026-05-13 19:18:04.390819+00	\N
44	FR	225C1154	\N	\N	ALTAMIR	AMBOISE SAS	2025-07-04	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1154/C9793687BB098BD663033E6439917178912A6215D9BCE88CC89765EDA50536D9.pdf	/repo/data/pdfs/fr/2025/225C1154.pdf	2026-05-13 19:18:05.434079+00	2026-05-13 19:18:05.434079+00	\N
45	FR	225C1153	\N	\N	BELIEVE	[pending parse]	2025-11-28	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1153/8D4F4D57519FB0DBC66686235B1CC114E7A7C3F0DF2FC2535D4ADE7E847BCC04.pdf	/repo/data/pdfs/fr/2025/225C1153.pdf	2026-05-13 19:18:06.603947+00	2026-05-13 19:18:06.603947+00	\N
46	FR	225C1139	\N	\N	ELECTRICITE ET EAUX DE MADAGASCAR	[pending parse]	2025-07-02	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1139/8BBACCFF5CC17C6941B15D31D95987856AAB9CD9E5EFEC4199D8BFA0098A9D2B.pdf	/repo/data/pdfs/fr/2025/225C1139.pdf	2026-05-13 19:18:07.630994+00	2026-05-13 19:18:07.630994+00	\N
47	FR	225C1003	\N	\N	ALTAMIR	AMBOISE SAS	2025-06-16	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1003/05ABE9DBA29A5ECF05C9F78B5AE905C73FB41BD48C6980F685BFE28737829D77.pdf	/repo/data/pdfs/fr/2025/225C1003.pdf	2026-05-13 19:18:08.774503+00	2026-05-13 19:18:08.774503+00	\N
48	FR	225C0995	\N	\N	GROUPE ETPO SA	GROUPE SPIE BATIGNOLLES SAS	2025-06-13	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0995/89F80B88B4C39CB8BE6C6E00CE15DED65CC13580E802F7616A1FF8EB217C8E76.pdf	/repo/data/pdfs/fr/2025/225C0995.pdf	2026-05-13 19:18:09.842221+00	2026-05-13 19:18:09.842221+00	\N
49	FR	225C0943	\N	\N	TARKETT S.A.	[pending parse]	2025-06-06	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0943/2766C94AB6689E31301176B6AB33C47F5BFA24283DFC719261629B63E795CE80.pdf	/repo/data/pdfs/fr/2025/225C0943.pdf	2026-05-13 19:18:11.070175+00	2026-05-13 19:18:11.070175+00	\N
50	FR	225C0929	\N	\N	VERALLIA	[pending parse]	2025-11-28	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0929/F0920AB04DC74434B52DD0FE7CB8BD0D0848FBCA912571968BD0585BAF6E0DA4.pdf	/repo/data/pdfs/fr/2025/225C0929.pdf	2026-05-13 19:18:12.104232+00	2026-05-13 19:18:12.104232+00	\N
51	FR	225C0921	\N	\N	M2I	ABILWAYS	2025-06-06	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0921/598AEEE4C8C8BA22E6E8F10899BF9587CAB180EDE7FD1370A2FC31000A928867.pdf	/repo/data/pdfs/fr/2025/225C0921.pdf	2026-05-13 19:18:14.158197+00	2026-05-13 19:18:14.158197+00	\N
52	FR	225C0920	\N	\N	BELIEVE	[pending parse]	2025-06-05	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0920/EFA14EF47EA8E982099F77768E6D5DB5982A1FB2DD38ADF653B80696FF46ED09.pdf	/repo/data/pdfs/fr/2025/225C0920.pdf	2026-05-13 19:18:15.265624+00	2026-05-13 19:18:15.265624+00	\N
53	FR	225C0845	\N	\N	UNIBEL	[pending parse]	2025-05-26	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0845/5959CDC36EEA75D9BB16F9817DF6C7314CE63D89790E33FEB1DA8C70DFF12CC7.pdf	/repo/data/pdfs/fr/2025/225C0845.pdf	2026-05-13 19:18:16.349676+00	2026-05-13 19:18:16.349676+00	\N
54	FR	225C0838	\N	\N	GROUPE ETPO SA	GROUPE SPIE BATIGNOLLES SAS	2025-05-22	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0838/7C5773E08924691DD74132E2C661DB3DE388B66A8E0BB41F5FADB7D71B0D3202.pdf	/repo/data/pdfs/fr/2025/225C0838.pdf	2026-05-13 19:18:17.355813+00	2026-05-13 19:18:17.355813+00	\N
55	FR	225C0741	\N	\N	FINANCIERE MONCEY	BOLLORE SE	2025-05-05	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0741/17E366B209E9E2ED0180EB9A7C7B00839735621223DF35947F824CB4EFE1E12D.pdf	/repo/data/pdfs/fr/2025/225C0741.pdf	2026-05-13 19:18:18.492276+00	2026-05-13 19:18:18.492276+00	\N
56	FR	225C0740	\N	\N	COMPAGNIE DU CAMBODGE	BOLLORE SE	2025-05-05	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0740/1283751425D68B1A5DF96C9EC10E51976B0C0CEE68842E85A9393EC463C78975.pdf	/repo/data/pdfs/fr/2025/225C0740.pdf	2026-05-13 19:18:19.624256+00	2026-05-13 19:18:19.624256+00	\N
57	FR	225C0739	\N	\N	SOCIETE INDUSTRIELLE ET FINANCIERE DE L'ARTOIS	BOLLORE SE	2025-11-28	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0739/49EDABB0E59E6DFB2185881C48662DD85049EDD259627F0F16D69C6A9FFDF6A4.pdf	/repo/data/pdfs/fr/2025/225C0739.pdf	2026-05-13 19:18:20.740774+00	2026-05-13 19:18:20.740774+00	\N
58	FR	225C0725	\N	\N	M2I	ABILWAYS	2025-06-06	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0725/686E4EA41EA6F49A0DDF69C4D06BBD4A0CE2D1FB6D7F3A165F8BB9E22B2AABE2.pdf	/repo/data/pdfs/fr/2025/225C0725.pdf	2026-05-13 19:18:21.895918+00	2026-05-13 19:18:21.895918+00	\N
59	FR	225C0708	\N	\N	VERALLIA	[pending parse]	2025-06-06	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0708/307129575A270937D25873228E87EF688B894D56B00E9385B4121A76FCC35177.pdf	/repo/data/pdfs/fr/2025/225C0708.pdf	2026-05-13 19:18:22.902183+00	2026-05-13 19:18:22.902183+00	\N
60	FR	225C0697	\N	\N	TARKETT S.A.	[pending parse]	2025-04-24	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0697/52E5D27DF0828B074AB7125AB17D808DC90C8DEEF08C87960D271D8CA892BFC6.pdf	/repo/data/pdfs/fr/2025/225C0697.pdf	2026-05-13 19:18:23.970107+00	2026-05-13 19:18:23.970107+00	\N
\.


--
-- Data for Name: events; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.events (id, deal_id, ts, event_type, description, source_url, raw_payload, created_at) FROM stdin;
1	1	2026-05-13 19:17:18.092124+00	filing_amf	BDIF note d'information OPR — visée: MEDIA 6 (numero 226C0661)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0661/954781AD2F1F1BF3816AA9C708025BF72D9C54D8CFCF908238AD85B40E413D3B.pdf	{"numero": "226C0661", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003282", "raison_sociale": "MEDIA 6"}], "documents": [{"path": "2026/226C0661/954781AD2F1F1BF3816AA9C708025BF72D9C54D8CFCF908238AD85B40E413D3B.pdf", "accessible": true, "nom_fichier": "226C0661.pdf"}, {"path": "2026/226C0661/A78F3F74555D43713BA6A4E7335EB02F7F97723CBB53196AFBB57737C335393B.pdf", "accessible": true, "nom_fichier": "226C066100.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-05-11T18:36:03.264749+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:18.077984+00
2	2	2026-05-13 19:17:19.087764+00	filing_amf	BDIF note d'information OPR — visée: MEDIA 6 (numero 226C0645)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0645/FE0616923D43D1F060E72056AFCF74F91E1A385883F3C547318A36E8027D6E2E.pdf	{"numero": "226C0645", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003282", "raison_sociale": "MEDIA 6"}], "documents": [{"path": "2026/226C0645/FE0616923D43D1F060E72056AFCF74F91E1A385883F3C547318A36E8027D6E2E.pdf", "accessible": true, "nom_fichier": "226C0645.pdf"}, {"path": "2026/226C0645/16C2EBE57BC3D54D636D0683B0E3627204B06A2020698C5809C8E5E48F47112F.pdf", "accessible": true, "nom_fichier": "226C064500.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-05-07T18:06:08.375648+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:19.08617+00
3	3	2026-05-13 19:17:20.114027+00	filing_amf	BDIF note d'information OPA — visée: FNAC DARTY (numero 226C0644)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0644/72DF20BE22E022A2C30DC6186B5CC3F77B31B85FA0D84EE9D1465AF96DF8A90C.pdf	{"numero": "226C0644", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005518", "raison_sociale": "FNAC DARTY"}], "documents": [{"path": "2026/226C0644/72DF20BE22E022A2C30DC6186B5CC3F77B31B85FA0D84EE9D1465AF96DF8A90C.pdf", "accessible": true, "nom_fichier": "226C0644.pdf"}, {"path": "2026/226C0644/18D9F8430751A07C88629CC435BD1B602E656443C533118CC0F1100EF8BC2403.pdf", "accessible": true, "nom_fichier": "226C064400.pdf"}, {"path": "2026/226C0644/541FFFF730DDD7000A6E588D16DD6DFD34B640308CF95D089AE442DB34E64D9E.pdf", "accessible": true, "nom_fichier": "226C064401.pdf"}, {"path": "2026/226C0644/9DB13672CA593901B7B8E8E95BCE77B84AEA0867E3C2DD0F0E24630DDE2F16FA.pdf", "accessible": true, "nom_fichier": "226C064402.pdf"}, {"path": "2026/226C0644/A53FB5CA3523408CB157219361FDBD07C147A48BBC5EFB2CAD3B151756BB98E8.pdf", "accessible": true, "nom_fichier": "226C064403.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2026-05-12T11:45:41.511658+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:20.112296+00
4	4	2026-05-13 19:17:21.188626+00	filing_amf	BDIF note d'information OPAS — visée: VINPAI (numero 226C0620)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0620/C88737C27EBA36B4ABE577D1CF942FADDF3FCB9A27BDA639FEA0105D816741C4.pdf	{"numero": "226C0620", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007943", "raison_sociale": "VINPAI"}], "documents": [{"path": "2026/226C0620/C88737C27EBA36B4ABE577D1CF942FADDF3FCB9A27BDA639FEA0105D816741C4.pdf", "accessible": true, "nom_fichier": "226C0620.pdf"}, {"path": "2026/226C0620/A842B4E896DB2C73C7F29CB6541C5930A0912BDBD16D8F4792FE5FD47D7C4510.pdf", "accessible": true, "nom_fichier": "226C062000.pdf"}, {"path": "2026/226C0620/DB5E46156AF748648D1C9ED6FFA1CE1E0820B4A1FA371A86FB3DA1A78EAE9BB6.pdf", "accessible": true, "nom_fichier": "226C062001.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2026-05-04T18:52:03.885698+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:21.186923+00
5	5	2026-05-13 19:17:22.235254+00	filing_amf	BDIF note d'information OPA — visée: ELECTRICITE ET EAUX DE MADAGASCAR (numero 226C0591)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0591/348695808BFBEBA6FD7244F05D2B43B6FB5C3DDBB70A75CFDDE0145335D82145.pdf	{"numero": "226C0591", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001534", "raison_sociale": "ELECTRICITE ET EAUX DE MADAGASCAR"}], "documents": [{"path": "2026/226C0591/348695808BFBEBA6FD7244F05D2B43B6FB5C3DDBB70A75CFDDE0145335D82145.pdf", "accessible": true, "nom_fichier": "226C0591.pdf"}, {"path": "2026/226C0591/FEB1B19F879934C47E2B995032733FBF0394C9D31EE247E1C32F6B29AF84B7D7.pdf", "accessible": true, "nom_fichier": "226C059100.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2026-04-28T08:06:04.306961+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:22.233159+00
6	6	2026-05-13 19:17:23.418991+00	filing_amf	BDIF note d'information OPAS — visée: POULAILLON (numero 226C0578)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0578/B956DC68725674FD12F3349D2160F0F214B32A3B47E1E2C948F36C10F05C7C1D.pdf	{"numero": "226C0578", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006037", "raison_sociale": "POULAILLON"}], "documents": [{"path": "2026/226C0578/B956DC68725674FD12F3349D2160F0F214B32A3B47E1E2C948F36C10F05C7C1D.pdf", "accessible": true, "nom_fichier": "226C0578.pdf"}, {"path": "2026/226C0578/E1AD7B3A6520A18790790C6234997ADD2C56B999F999A75DB4DE7A75B7F97D21.pdf", "accessible": true, "nom_fichier": "226C057800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2026-04-23T18:00:03.924818+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:23.417253+00
13	13	2026-05-13 19:17:31.002633+00	filing_amf	BDIF note d'information OPA — visée: FNAC DARTY (numero 226C0287)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0287/DBE2E400A000FC29A55CD25156BC15A62A7E389B563ED4E91BC02C772EA0F33F.pdf	{"numero": "226C0287", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005518", "raison_sociale": "FNAC DARTY"}], "documents": [{"path": "2026/226C0287/DBE2E400A000FC29A55CD25156BC15A62A7E389B563ED4E91BC02C772EA0F33F.pdf", "accessible": true, "nom_fichier": "226C0287.pdf"}, {"path": "2026/226C0287/824D3062B190C817B7A4E5D07863722F17686091FDC4D342E7E27F733B9AA6B6.pdf", "accessible": true, "nom_fichier": "226C028700.pdf"}, {"path": "2026/226C0287/41982AC74DB402CBCE4E559CE1EB4160081D7A826E4612E383B9D6271AE0A583.pdf", "accessible": true, "nom_fichier": "226C028701.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2026-03-12T16:38:03.728842+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:31.001087+00
7	7	2026-05-13 19:17:24.508693+00	filing_amf	BDIF note d'information OPR — visée: TERACT (numero 226C0550)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0550/790CEA3A90861D7F49FCC7EC86FDEE425D31E42EEA5597D127F45DCF68783FB8.pdf	{"numero": "226C0550", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007211", "raison_sociale": "TERACT"}], "documents": [{"path": "2026/226C0550/790CEA3A90861D7F49FCC7EC86FDEE425D31E42EEA5597D127F45DCF68783FB8.pdf", "accessible": true, "nom_fichier": "226C0550.pdf"}, {"path": "2026/226C0550/62A8D6328F183E53AF0F1067FD6F67A0624E5BB41B18D9408F04FF576738B7BB.pdf", "accessible": true, "nom_fichier": "226C055000.pdf"}, {"path": "2026/226C0550/6A7B9D3A5756581539366032643CE0298AE74A588BB1D52FFD7AF2575A4446F5.pdf", "accessible": true, "nom_fichier": "226C055001.pdf"}, {"path": "2026/226C0550/01D20837BA9794A8678E8D6289B556AD4596AF630A4F9A255BA407512E1A7C1A.pdf", "accessible": true, "nom_fichier": "226C055002.pdf"}, {"path": "2026/226C0550/9FDB2188C43A9108A8275646608079AEC0818A898823F7E0C6AEC7406132C10D.pdf", "accessible": true, "nom_fichier": "226C055003.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-04-20T17:54:04.035013+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:24.506542+00
8	8	2026-05-13 19:17:25.68524+00	filing_amf	BDIF note d'information OPR — visée: SOCIETE DE LA TOUR EIFFEL (numero 226C0538)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0538/F1A0A887F62CDDB65C1D688EA3F99A87CCBF26975A738C848CFAF5EB83C3E9AB.pdf	{"numero": "226C0538", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001493", "raison_sociale": "SOCIETE DE LA TOUR EIFFEL"}], "documents": [{"path": "2026/226C0538/F1A0A887F62CDDB65C1D688EA3F99A87CCBF26975A738C848CFAF5EB83C3E9AB.pdf", "accessible": true, "nom_fichier": "226C0538.pdf"}, {"path": "2026/226C0538/25B741123069FBC4D61F9B59471449E098DDCDFB6D48897AE9DCD5B1D79BAD7D.pdf", "accessible": true, "nom_fichier": "226C053800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-04-17T17:38:03.555332+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:25.683835+00
9	9	2026-05-13 19:17:26.75969+00	filing_amf	BDIF note d'information OPR — visée: MEDIA 6 (numero 226C0531)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0531/561AA4EE77DE083659474F2355A75F1A1AFA156AD34FED1FC6872CCF0A07CE87.pdf	{"numero": "226C0531", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003282", "raison_sociale": "MEDIA 6"}], "documents": [{"path": "2026/226C0531/561AA4EE77DE083659474F2355A75F1A1AFA156AD34FED1FC6872CCF0A07CE87.pdf", "accessible": true, "nom_fichier": "226C0531.pdf"}, {"path": "2026/226C0531/46CD7E6A422170B10E4FF91220D5709F1AA4F58DDBCD130C2B95EADC69D288E3.pdf", "accessible": true, "nom_fichier": "226C053100.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-04-16T18:20:05.849225+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:26.75835+00
10	10	2026-05-13 19:17:27.861191+00	filing_amf	BDIF note d'information OPR — visée: GAUMONT (numero 226C0511)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0511/AB617FF3C053B29C0869579FC6C94E567E94EF5CA54AD731BEFC90096BF14FB9.pdf	{"numero": "226C0511", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003344", "raison_sociale": "GAUMONT"}], "documents": [{"path": "2026/226C0511/AB617FF3C053B29C0869579FC6C94E567E94EF5CA54AD731BEFC90096BF14FB9.pdf", "accessible": true, "nom_fichier": "226C0511.pdf"}, {"path": "2026/226C0511/1F861B203CC9A83794E4B23052AFA9661EC88CB447C7B30637A44FE4660FB0AA.pdf", "accessible": true, "nom_fichier": "226C051100.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-04-13T18:48:03.436421+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:27.859692+00
11	11	2026-05-13 19:17:28.912754+00	filing_amf	BDIF note d'information OPR — visée: BALYO (numero 226C0347)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0347/0B2F7A8AF7A42A5DB26EAA3C63A63EAEB4397FC23899488D3EE974E2276033AD.pdf	{"numero": "226C0347", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006437", "raison_sociale": "BALYO"}], "documents": [{"path": "2026/226C0347/0B2F7A8AF7A42A5DB26EAA3C63A63EAEB4397FC23899488D3EE974E2276033AD.pdf", "accessible": true, "nom_fichier": "226C0347.pdf"}, {"path": "2026/226C0347/3134C747EE8DAE1498BC80E42178A379592F1A003FA4D59E32EE8399C88DC870.pdf", "accessible": true, "nom_fichier": "226C034700.pdf"}, {"path": "2026/226C0347/4BA9FF38A00BCF72BFE3D3648B78D40C1C0E71DE87E7388E334429856FE4EF85.pdf", "accessible": true, "nom_fichier": "226C034701.pdf"}, {"path": "2026/226C0347/1C313FC88D91EE393AD161781DEBA691B25B3A349F6D408AE1CB1CEB9352758D.pdf", "accessible": true, "nom_fichier": "226C034702.pdf"}, {"path": "2026/226C0347/6B82B960E85542445EC283217BB50452CD7D1FC65FDDCCEA333248BD28AEBC4F.pdf", "accessible": true, "nom_fichier": "226C034703.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-03-19T18:12:08.813352+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:28.911507+00
12	12	2026-05-13 19:17:29.871017+00	filing_amf	BDIF note d'information OPR — visée: MEDIA 6 (numero 226C0318)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0318/2E2150D58F6F479C2C8EF560F6397E1558E9AF7DDB22A89699FC6027C7914D34.pdf	{"numero": "226C0318", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003282", "raison_sociale": "MEDIA 6"}], "documents": [{"path": "2026/226C0318/2E2150D58F6F479C2C8EF560F6397E1558E9AF7DDB22A89699FC6027C7914D34.pdf", "accessible": true, "nom_fichier": "226C0318.pdf"}, {"path": "2026/226C0318/EF0A7650F909E5770149C02A5FF714B769F0E8F7DAF67ACE6FD786BB8B0EFDD9.pdf", "accessible": true, "nom_fichier": "226C031800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-03-16T17:42:03.641407+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:29.86892+00
14	14	2026-05-13 19:17:32.192037+00	filing_amf	BDIF note d'information OPR — visée: TERACT (numero 226C0278)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0278/A31DB49A0FE6CB4A382C7B960FF679D3F9018C80059A4C02ECC31EB5E653A6CE.pdf	{"numero": "226C0278", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007211", "raison_sociale": "TERACT"}], "documents": [{"path": "2026/226C0278/A31DB49A0FE6CB4A382C7B960FF679D3F9018C80059A4C02ECC31EB5E653A6CE.pdf", "accessible": true, "nom_fichier": "226C0278.pdf"}, {"path": "2026/226C0278/43D096BA1C3B2A0FCA0150F896D27D17768F4ED4DCC9809DE880426A377D0EB5.pdf", "accessible": true, "nom_fichier": "226C027800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-03-09T17:58:03.433870+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:32.190677+00
15	15	2026-05-13 19:17:33.34022+00	filing_amf	BDIF note d'information OPRA — visée: GROUPE TERA (numero 226C0210)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0210/1C1F1BF8B08724AE8CC9283B6501A90015C258F03837A071E732589AE12E82E0.pdf	{"numero": "226C0210", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006841", "raison_sociale": "GROUPE TERA"}], "documents": [{"path": "2026/226C0210/1C1F1BF8B08724AE8CC9283B6501A90015C258F03837A071E732589AE12E82E0.pdf", "accessible": true, "nom_fichier": "226C0210.pdf"}, {"path": "2026/226C0210/D87475DAF86F200458826406D143B817006C0A05A84BFC6D00284C3A1E213E05.pdf", "accessible": true, "nom_fichier": "226C021000.pdf"}, {"path": "2026/226C0210/DF30F144E8A6ACEF2B03E7389F67801FE337F3443A44CF24A15F94D07463D27C.pdf", "accessible": true, "nom_fichier": "226C021001.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions", "ObligationDepotOP"], "types_operation": ["OPRA"], "date_information": null, "date_publication": "2026-02-19T17:44:03.849839+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:33.338266+00
16	16	2026-05-13 19:17:34.508863+00	filing_amf	BDIF note d'information OPR — visée: TERACT (numero 226C0157)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0157/2954E3860C1959ADF0F7724A2D2E9CF1D89B305D888D3417CE3DF95E46E1D798.pdf	{"numero": "226C0157", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007211", "raison_sociale": "TERACT"}], "documents": [{"path": "2026/226C0157/2954E3860C1959ADF0F7724A2D2E9CF1D89B305D888D3417CE3DF95E46E1D798.pdf", "accessible": true, "nom_fichier": "226C0157.pdf"}, {"path": "2026/226C0157/B9B744E6391FDBE26A645BB267357A04841128BEB0C61F8A30BD48A5DC015F0C.pdf", "accessible": true, "nom_fichier": "226C015700.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-02-05T18:36:23.745035+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:34.507308+00
17	17	2026-05-13 19:17:35.538109+00	filing_amf	BDIF note d'information OPRA — visée: UV GERMI (numero 226C0156)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0156/66D132B49FB29CB455C97C16A2949728C4D3153D4E3A35EF0F7E7B5E8B9D09CD.pdf	{"numero": "226C0156", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006455", "raison_sociale": "UV GERMI"}], "documents": [{"path": "2026/226C0156/66D132B49FB29CB455C97C16A2949728C4D3153D4E3A35EF0F7E7B5E8B9D09CD.pdf", "accessible": true, "nom_fichier": "226C0156.pdf"}, {"path": "2026/226C0156/C4F529053034B8FB641910F3AE3F8363BC42FCC286D08B5708670C1D7EACA2EB.pdf", "accessible": true, "nom_fichier": "226C015600.pdf"}, {"path": "2026/226C0156/9AA900CB2BE829402B0EE390DCC152F4DEF55C51F132757B757CC913E4EC0853.pdf", "accessible": true, "nom_fichier": "226C015601.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPRA"], "date_information": null, "date_publication": "2026-02-05T18:12:03.559156+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:35.535691+00
18	18	2026-05-13 19:17:36.542187+00	filing_amf	BDIF note d'information OPAS — visée: SOCIETE DE TAYNINH (numero 226C0095)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0095/69C403AC9DB64955C7CF92305B5B134E2AD8BE64C70A33B64DE758B67E616C68.pdf	{"numero": "226C0095", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00002983", "raison_sociale": "SOCIETE DE TAYNINH"}], "documents": [{"path": "2026/226C0095/69C403AC9DB64955C7CF92305B5B134E2AD8BE64C70A33B64DE758B67E616C68.pdf", "accessible": true, "nom_fichier": "226C0095.pdf"}, {"path": "2026/226C0095/4FB2DC27D0FDCF38064631F24C61EDC2CF01CA2060540A6AC557D40B8CD77574.pdf", "accessible": true, "nom_fichier": "226C009500.pdf"}, {"path": "2026/226C0095/0D7D61E06C293A8796083FB566FFA2C5A489640D9C4F034FFDD477DDD50BBA84.pdf", "accessible": true, "nom_fichier": "226C009501.pdf"}, {"path": "2026/226C0095/69F72D0CDB02A80F1D066A41DDD65916E9D818932FAFF7D2921EB310EE95FDE9.pdf", "accessible": true, "nom_fichier": "226C009502.pdf"}, {"path": "2026/226C0095/4D5E7F38C9C44968C1C2C0C85E181143172504E9DDD054C034FA66DEA0EEB6F7.pdf", "accessible": true, "nom_fichier": "226C009503.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2026-01-23T18:04:03.279555+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:36.540198+00
19	19	2026-05-13 19:17:37.717854+00	filing_amf	BDIF note d'information OPR — visée: BALYO (numero 226C0020)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0020/DFF429DF18AF43BC18E7971ABF71A2F5B90B0255B4EBB18EB268F6D1579C2074.pdf	{"numero": "226C0020", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006437", "raison_sociale": "BALYO"}], "documents": [{"path": "2026/226C0020/DFF429DF18AF43BC18E7971ABF71A2F5B90B0255B4EBB18EB268F6D1579C2074.pdf", "accessible": true, "nom_fichier": "226C0020.pdf"}, {"path": "2026/226C0020/FC9756843C80D897883419B09813EC70BDB33A564C55CB13555313D329298372.pdf", "accessible": true, "nom_fichier": "226C002000.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-01-07T10:48:45.670794+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:37.715859+00
20	20	2026-05-13 19:17:38.920827+00	filing_amf	BDIF note d'information OPRA — visée: GROUPE TERA (numero 226C0008)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0008/CFFC2BF9EC93BB0D5C735AC1596CCD7BAE08ACB2F02F38BE5E387266621C223E.pdf	{"numero": "226C0008", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006841", "raison_sociale": "GROUPE TERA"}], "documents": [{"path": "2026/226C0008/CFFC2BF9EC93BB0D5C735AC1596CCD7BAE08ACB2F02F38BE5E387266621C223E.pdf", "accessible": true, "nom_fichier": "226C0008.pdf"}, {"path": "2026/226C0008/77073798CB5A2CA59C4F1CC62576052BE56474525F19A2529344564932DFDDDD.pdf", "accessible": true, "nom_fichier": "226C000800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPRA"], "date_information": null, "date_publication": "2026-01-05T18:42:02.720425+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:38.919197+00
39	39	2026-05-13 19:17:59.943824+00	filing_amf	BDIF note d'information OPAS — visée: AGROGENERATION (numero 225C1439)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1439/24F7E7C9EB30188B5FD0914078F16AB748E20D5EE7649132863B135FE4017D31.pdf	{"numero": "225C1439", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005064", "raison_sociale": "AGROGENERATION"}], "documents": [{"path": "2025/225C1439/24F7E7C9EB30188B5FD0914078F16AB748E20D5EE7649132863B135FE4017D31.pdf", "accessible": true, "nom_fichier": "225C1439.pdf"}, {"path": "2025/225C1439/069CE223115C4D35F0C172C045200E251ECD46C43E76D9CDF8E04E01C2BDD055.pdf", "accessible": true, "nom_fichier": "225C143900.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-08-26T17:10:04.157496+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:59.94233+00
21	21	2026-05-13 19:17:40.103507+00	filing_amf	BDIF note d'information OPR — visée: PRODWARE (numero 225C2156)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2156/ADFDAA0E32B9156501354BF7041F099EE4B743B76ED64C90DE8EB363A1ABCD88.pdf	{"numero": "225C2156", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00004376", "raison_sociale": "PRODWARE"}, {"role": "Initiateur", "jeton": "RS00007540", "raison_sociale": "PHAST INVEST"}], "documents": [{"path": "2025/225C2156/ADFDAA0E32B9156501354BF7041F099EE4B743B76ED64C90DE8EB363A1ABCD88.pdf", "accessible": true, "nom_fichier": "225C2156.pdf"}, {"path": "2025/225C2156/FF4583CCBCC12F33A41E3E94E25DB7DA8E86A119F325214FACCE8D2FDB4B671D.pdf", "accessible": true, "nom_fichier": "225C215600.pdf"}, {"path": "2025/225C2156/506DEF6416E2AFC69FFD8797DBDB41CF7571F5BA4FBBC2CE37E963C448FD4250.pdf", "accessible": true, "nom_fichier": "225C215601.pdf"}, {"path": "2025/225C2156/D6EC858E11C34AF6AC6ED5AC2FA5D25A54102AFC8DD37077070B25325C7ED373.pdf", "accessible": true, "nom_fichier": "225C215602.pdf"}, {"path": "2025/225C2156/CE2ECF9DC3DAD4BD107FFD14F2DDB9B2EA86C63945B371AEBD92A37C844FFDA1.pdf", "accessible": true, "nom_fichier": "225C215603.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-01-23T16:28:04.653358+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:40.102151+00
22	22	2026-05-13 19:17:41.05231+00	filing_amf	BDIF note d'information OPRA — visée: UV GERMI (numero 225C2136)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2136/B94BBB38882DB1DDE9148BF8D7FD9AF90D3A1681299822A01FC9104155FA4E48.pdf	{"numero": "225C2136", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006455", "raison_sociale": "UV GERMI"}], "documents": [{"path": "2025/225C2136/B94BBB38882DB1DDE9148BF8D7FD9AF90D3A1681299822A01FC9104155FA4E48.pdf", "accessible": true, "nom_fichier": "225C2136.pdf"}, {"path": "2025/225C2136/5A0B405CD03DDF70B5AE3E6A5A842411F069BE4DC542150C891274FBECC6B40F.pdf", "accessible": true, "nom_fichier": "225C213600.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPRA"], "date_information": null, "date_publication": "2025-12-16T18:58:05.793706+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:41.050517+00
23	23	2026-05-13 19:17:42.096815+00	filing_amf	BDIF note d'information OPA — visée: ELECTRICITE ET EAUX DE MADAGASCAR (numero 225C2135)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2135/5C51631DA1F169C7D81C593980694A6CCD25AE6C6A562F86302C14EDCD2F0C92.pdf	{"numero": "225C2135", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001534", "raison_sociale": "ELECTRICITE ET EAUX DE MADAGASCAR"}], "documents": [{"path": "2025/225C2135/5C51631DA1F169C7D81C593980694A6CCD25AE6C6A562F86302C14EDCD2F0C92.pdf", "accessible": true, "nom_fichier": "225C2135.pdf"}, {"path": "2025/225C2135/E586C60EBE7E7792572B5B5BB29769CB1B3CA5001B9AEE8E046FFC1CF9E9DB07.pdf", "accessible": true, "nom_fichier": "225C213500.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2025-12-17T11:06:04.303527+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:42.094803+00
24	24	2026-05-13 19:17:43.278026+00	filing_amf	BDIF note d'information OPAS — visée: SOCIETE DE TAYNINH (numero 225C2081)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2081/8CC4832C7F06C4C44A2C8A3798DA63476B655465D14B3460FE2B3DE3C7020FD0.pdf	{"numero": "225C2081", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00002983", "raison_sociale": "SOCIETE DE TAYNINH"}], "documents": [{"path": "2025/225C2081/8CC4832C7F06C4C44A2C8A3798DA63476B655465D14B3460FE2B3DE3C7020FD0.pdf", "accessible": true, "nom_fichier": "225C2081.pdf"}, {"path": "2025/225C2081/1CB74CB3B9731996E10C607A7425CFAAC85E59ECCB0383F7C8074BF461C72941.pdf", "accessible": true, "nom_fichier": "225C208100.pdf"}, {"path": "2025/225C2081/967CDF7AFC396FDB154CCDCE36CB06C040DBD75D4CF11063494C1C677012E0A9.pdf", "accessible": true, "nom_fichier": "225C208101.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-12-08T17:42:03.922729+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:43.276713+00
25	25	2026-05-13 19:17:44.409777+00	filing_amf	BDIF note d'information OPR — visée: BALYO (numero 225C2063)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2063/4B74E67D96D0415272C70A7A4D4DC3BBE94E2C570A5E4BFFDAB4B0F44776363F.pdf	{"numero": "225C2063", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006437", "raison_sociale": "BALYO"}], "documents": [{"path": "2025/225C2063/4B74E67D96D0415272C70A7A4D4DC3BBE94E2C570A5E4BFFDAB4B0F44776363F.pdf", "accessible": true, "nom_fichier": "225C2063.pdf"}, {"path": "2025/225C2063/94B3F05654D718554CFF1253A7167E0315B809523E2A3B9A484E0D17E0262D3B.pdf", "accessible": true, "nom_fichier": "225C206300.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-01-22T16:22:03.563591+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:44.408302+00
26	26	2026-05-13 19:17:45.497745+00	filing_amf	BDIF note d'information OPAS — visée: COGELEC (numero 225C2061)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2061/1BE71CDDD093C59BF3C0816994D45C9364CA1D5E1088325B1A6E64CC57C7F564.pdf	{"numero": "225C2061", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006594", "raison_sociale": "COGELEC"}], "documents": [{"path": "2025/225C2061/1BE71CDDD093C59BF3C0816994D45C9364CA1D5E1088325B1A6E64CC57C7F564.pdf", "accessible": true, "nom_fichier": "225C2061.pdf"}, {"path": "2025/225C2061/FF3628690D829BAED7483D2B591ECD0D7F4A6E8E9F4A5F18403623C858587482.pdf", "accessible": true, "nom_fichier": "225C206100.pdf"}, {"path": "2025/225C2061/A0D39344E7D6966FFAA0650F8E8B05B70BE6B98F26A28B8DFDB5C5778A66D96A.pdf", "accessible": true, "nom_fichier": "225C206101.pdf"}, {"path": "2025/225C2061/9827797F2577B1D58D1EA624F05F701FB91DAB226A1E58D12AACAAE6B71D658C.pdf", "accessible": true, "nom_fichier": "225C206102.pdf"}, {"path": "2025/225C2061/2FB9018E61D2C3EF250BAC49A78C7E4F6E4726E657436A0BAD8E9156531F2199.pdf", "accessible": true, "nom_fichier": "225C206103.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2026-01-22T16:36:03.701429+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:45.495554+00
27	27	2026-05-13 19:17:46.696221+00	filing_amf	BDIF note d'information OPAS — visée: WAGA ENERGY (numero 225C1971)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1971/1561FA645F4D0517BB7B8C3D54435902C7D730202735D1145A8BF8C250D66A3C.pdf	{"numero": "225C1971", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007433", "raison_sociale": "WAGA ENERGY"}], "documents": [{"path": "2025/225C1971/1561FA645F4D0517BB7B8C3D54435902C7D730202735D1145A8BF8C250D66A3C.pdf", "accessible": true, "nom_fichier": "225C1971.pdf"}, {"path": "2025/225C1971/5EE932D9660BB27974F9BDFE36A092E0373355267A490AE6715D9C32933E7F49.pdf", "accessible": true, "nom_fichier": "225C197100.pdf"}, {"path": "2025/225C1971/A8E0778FA3CC87F8A5E219AC2E7BCB6539468667FCDEC8A76810093A8A18BB06.pdf", "accessible": true, "nom_fichier": "225C197101.pdf"}, {"path": "2025/225C1971/7F3D3AC03DC549DABE0F71E1D2DD885C203D62BE00A415A1029367CA17955662.pdf", "accessible": true, "nom_fichier": "225C197102.pdf"}, {"path": "2025/225C1971/4CC4C2226AD906BA1B4114E7C9447005DC173F10FCC1E8EE662F5507EA90EB8A.pdf", "accessible": true, "nom_fichier": "225C197103.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-11-24T09:56:03.676992+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:46.694968+00
28	28	2026-05-13 19:17:47.604041+00	filing_amf	BDIF note d'information OPR — visée: PRODWARE (numero 225C1924)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1924/278CEE170D11B4B719A5AF39E6EF5D5D98777BCB414E8E0447C8A4C43B17A99C.pdf	{"numero": "225C1924", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00004376", "raison_sociale": "PRODWARE"}, {"role": "Initiateur", "jeton": "RS00007540", "raison_sociale": "PHAST INVEST"}], "documents": [{"path": "2025/225C1924/278CEE170D11B4B719A5AF39E6EF5D5D98777BCB414E8E0447C8A4C43B17A99C.pdf", "accessible": true, "nom_fichier": "225C1924.pdf"}, {"path": "2025/225C1924/740A0D1F6EE2E48B6226EE3D7B33180D14BD955ABFCD6FC62C75755E8D51C787.pdf", "accessible": true, "nom_fichier": "225C192400.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-11-14T16:08:03.946506+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:47.602666+00
29	29	2026-05-13 19:17:48.768332+00	filing_amf	BDIF note d'information OPR — visée: TRONIC'S MICROSYSTEMS S.A. (numero 225C1884)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1884/B2E25865C4580D8F7E0BAA669B6652F2AF700806DAAE34F81EBEE76DC60766A8.pdf	{"numero": "225C1884", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005911", "raison_sociale": "TRONIC'S MICROSYSTEMS S.A."}, {"role": "Initiateur", "jeton": "RS00007557", "raison_sociale": "TDK ELECTRONICS AG"}], "documents": [{"path": "2025/225C1884/B2E25865C4580D8F7E0BAA669B6652F2AF700806DAAE34F81EBEE76DC60766A8.pdf", "accessible": true, "nom_fichier": "225C1884.pdf"}, {"path": "2025/225C1884/1B8FE724D376A7F8E214F4D22166340DC9DA6592839C6E1AF75D5C3C80B9AC48.pdf", "accessible": true, "nom_fichier": "225C188400.pdf"}, {"path": "2025/225C1884/BD2D1A20676E8301501A16EC860E3AE85525635146ADBE9BA3BE381ABABE54D3.pdf", "accessible": true, "nom_fichier": "225C188401.pdf"}, {"path": "2025/225C1884/581AB41E8387DFCBA952EB3E8A4C1550981957E125D75798526A644057066DA9.pdf", "accessible": true, "nom_fichier": "225C188402.pdf"}, {"path": "2025/225C1884/79C4D536B85F91000305A96D8F35524001CED5C3B06FB6B644AFCD10BC8554A2.pdf", "accessible": true, "nom_fichier": "225C188403.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-11-13T10:19:20.949769+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:48.766949+00
30	30	2026-05-13 19:17:49.897414+00	filing_amf	BDIF note d'information OPR — visée: PRODWARE (numero 225C1797)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1797/18E0F87ABC999B41EECECC8FE71915ACAC89A921DE6C878FBDFA509EEE420DDE.pdf	{"numero": "225C1797", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00004376", "raison_sociale": "PRODWARE"}, {"role": "Initiateur", "jeton": "RS00007540", "raison_sociale": "PHAST INVEST"}], "documents": [{"path": "2025/225C1797/18E0F87ABC999B41EECECC8FE71915ACAC89A921DE6C878FBDFA509EEE420DDE.pdf", "accessible": true, "nom_fichier": "225C1797.pdf"}, {"path": "2025/225C1797/83991376C1D4E98D96D953AD711C3A814BC0CAC07FBB0A8A4C2718DE7AB14880.pdf", "accessible": true, "nom_fichier": "225C179700.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-10-24T14:50:03.300838+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:49.895708+00
31	31	2026-05-13 19:17:51.102168+00	filing_amf	BDIF note d'information OPA — visée: VOGO (numero 225C1794)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1794/46A8BC8D13F4BFEE1C3F6C7EA75130F3F12717FB75CF6FF6F406DE51A430F10E.pdf	{"numero": "225C1794", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006663", "raison_sociale": "VOGO"}, {"role": "Initiateur", "jeton": "RS00006263", "raison_sociale": "ABEO"}], "documents": [{"path": "2025/225C1794/46A8BC8D13F4BFEE1C3F6C7EA75130F3F12717FB75CF6FF6F406DE51A430F10E.pdf", "accessible": true, "nom_fichier": "225C1794.pdf"}, {"path": "2025/225C1794/A9776B3B941EB44B9C2F6F054D9DF6228B712C3A0D9295387AE71A66357407C7.pdf", "accessible": true, "nom_fichier": "225C179400.pdf"}, {"path": "2025/225C1794/5AAF67FC88026DE37210533BB31C7C64CC3E6F8673C1A745C38D5ED9DC322917.pdf", "accessible": true, "nom_fichier": "225C179401.pdf"}, {"path": "2025/225C1794/782AFA50EA08DD180BABA5B9192149D211428136A1494B83114C754C0CE54CD9.pdf", "accessible": true, "nom_fichier": "225C179402.pdf"}, {"path": "2025/225C1794/5CB7A69744ABFEBED229F405B9963F7F2D74298FA4B1B0EA34306A843E6FB4D5.pdf", "accessible": true, "nom_fichier": "225C179403.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPA", "OPE"], "date_information": null, "date_publication": "2025-11-28T10:58:03.494129+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:51.100418+00
32	32	2026-05-13 19:17:52.330327+00	filing_amf	BDIF note d'information OPAS — visée: COGELEC (numero 225C1755)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1755/AA36F6148357F70B3CEA5A545CC6F7C5082938EC4B57FCFF4588A719CA34AB0D.pdf	{"numero": "225C1755", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006594", "raison_sociale": "COGELEC"}], "documents": [{"path": "2025/225C1755/AA36F6148357F70B3CEA5A545CC6F7C5082938EC4B57FCFF4588A719CA34AB0D.pdf", "accessible": true, "nom_fichier": "225C1755.pdf"}, {"path": "2025/225C1755/D8E8118785D5D2F62FE03203BD2B410E7B50F25FCA7320B7BA2B24B35D0D7190.pdf", "accessible": true, "nom_fichier": "225C175500.pdf"}, {"path": "2025/225C1755/4781806250AE9E0DB39158048E12177DD27DE66FB22A37E4D62CF112A52D4559.pdf", "accessible": true, "nom_fichier": "225C175501.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-10-15T17:12:04.283194+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:52.328811+00
33	33	2026-05-13 19:17:53.335186+00	filing_amf	BDIF note d'information OPAS — visée: AGROGENERATION (numero 225C1734)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1734/B3BE65DA8A38EFEF0C6E0B463784BE812AFE929914A3F3416AE80A2CF9A7818E.pdf	{"numero": "225C1734", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005064", "raison_sociale": "AGROGENERATION"}], "documents": [{"path": "2025/225C1734/B3BE65DA8A38EFEF0C6E0B463784BE812AFE929914A3F3416AE80A2CF9A7818E.pdf", "accessible": true, "nom_fichier": "225C1734.pdf"}, {"path": "2025/225C1734/8537D82FACF7C7F1A9C372ACFA8298A2A889E4A485C4D7C80A88A81AC2D4457A.pdf", "accessible": true, "nom_fichier": "225C173400.pdf"}, {"path": "2025/225C1734/D00A905237F64C10F908E3B32D4CF97377EFF231D0B35C506A3359C59B77B701.pdf", "accessible": true, "nom_fichier": "225C173401.pdf"}, {"path": "2025/225C1734/153035C84E493267EFEE5CE74DDA7D13D73F927A3966F51607FC459972151465.pdf", "accessible": true, "nom_fichier": "225C173402.pdf"}, {"path": "2025/225C1734/856EF871EE860CCFFB1BEBE90AE6470B1DA814B8EAB3E7F3B0D2EB5D4B9C9BEC.pdf", "accessible": true, "nom_fichier": "225C173403.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-10-13T08:16:04.057378+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:53.333811+00
34	34	2026-05-13 19:17:54.55523+00	filing_amf	BDIF note d'information OPAS — visée: WAGA ENERGY (numero 225C1666)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1666/A2460CAD381A8AA7A5E0566E2B02915BD2C21EB7F7F41119354BA67BBCF0C01E.pdf	{"numero": "225C1666", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007433", "raison_sociale": "WAGA ENERGY"}], "documents": [{"path": "2025/225C1666/A2460CAD381A8AA7A5E0566E2B02915BD2C21EB7F7F41119354BA67BBCF0C01E.pdf", "accessible": true, "nom_fichier": "225C1666.pdf"}, {"path": "2025/225C1666/C3424E872C1C3A98D38DA5D776077355D6848AA6513483E0C5EB0F67021D4BD6.pdf", "accessible": true, "nom_fichier": "225C166600.pdf"}, {"path": "2025/225C1666/B5555690F68297698897C6A404EDAAA62698E253E49AAE85C151D892955CF16B.pdf", "accessible": true, "nom_fichier": "225C166601.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-10-02T09:18:03.601483+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:54.553418+00
35	35	2026-05-13 19:17:55.584679+00	filing_amf	BDIF note d'information OPR — visée: TRONIC'S MICROSYSTEMS S.A. (numero 225C1665)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1665/4BCBC4A976AD1A11A4CFC01F982000092C433608C9B947BF53BA5D350947542F.pdf	{"numero": "225C1665", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005911", "raison_sociale": "TRONIC'S MICROSYSTEMS S.A."}, {"role": "Initiateur", "jeton": "RS00007557", "raison_sociale": "TDK ELECTRONICS AG"}], "documents": [{"path": "2025/225C1665/4BCBC4A976AD1A11A4CFC01F982000092C433608C9B947BF53BA5D350947542F.pdf", "accessible": true, "nom_fichier": "225C1665.pdf"}, {"path": "2025/225C1665/5E5074D4E8D6F3BB6346C689893055F94EFED6EF471B3F4C880B9955683269D6.pdf", "accessible": true, "nom_fichier": "225C166500.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-10-01T14:20:03.398565+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:55.582848+00
36	36	2026-05-13 19:17:56.762958+00	filing_amf	BDIF note d'information OPAS — visée: AMPLITUDE SURGICAL (numero 225C1629)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1629/8DF9E6C891A17EFCBB495FC63F9C7982DA9D8429C2BCBDA248C9DD77B85D97C3.pdf	{"numero": "225C1629", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006019", "raison_sociale": "AMPLITUDE SURGICAL"}], "documents": [{"path": "2025/225C1629/8DF9E6C891A17EFCBB495FC63F9C7982DA9D8429C2BCBDA248C9DD77B85D97C3.pdf", "accessible": true, "nom_fichier": "225C1629.pdf"}, {"path": "2025/225C1629/33D3BD53F5D38563AD13D90148C74AEAC768A8F81A688059898AA65F5A47DE4C.pdf", "accessible": true, "nom_fichier": "225C162900.pdf"}, {"path": "2025/225C1629/59C67C4ABD2FFBA7CC459314FCBB3FA821EDE9BCAF1FD2A34CEB2F4066BEDA7A.pdf", "accessible": true, "nom_fichier": "225C162901.pdf"}, {"path": "2025/225C1629/54EB5C5BF108163EDA8F96E96EE3C2119807F6203E1D2AE8F0467F60276B30E9.pdf", "accessible": true, "nom_fichier": "225C162902.pdf"}, {"path": "2025/225C1629/6206DAC040E5C9AB7D18454D662BD625EA8E705F4B88F47820A7663C4490697D.pdf", "accessible": true, "nom_fichier": "225C162903.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-11-28T11:04:03.209273+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:56.760958+00
37	37	2026-05-13 19:17:57.771092+00	filing_amf	BDIF note d'information OPAS — visée: ALTAMIR (numero 225C1529)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1529/B5E5B14DB09B63248AD314DE0677266181D86CE9711A330BBDDE64135A76DED8.pdf	{"numero": "225C1529", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003545", "raison_sociale": "ALTAMIR"}, {"role": "Initiateur", "jeton": "RS00005821", "raison_sociale": "AMBOISE SAS"}], "documents": [{"path": "2025/225C1529/B5E5B14DB09B63248AD314DE0677266181D86CE9711A330BBDDE64135A76DED8.pdf", "accessible": true, "nom_fichier": "225C1529.pdf"}, {"path": "2025/225C1529/664F0718D82AECC22A0383F7C96085EE0628EE3A636BB0E6355D77BEC5A90B28.pdf", "accessible": true, "nom_fichier": "225C152900.pdf"}, {"path": "2025/225C1529/45C4EB8CC6B1B2D2B47429CE70F22E9D4E00EEF8729696444CF73AEEAAE55522.pdf", "accessible": true, "nom_fichier": "225C152901.pdf"}, {"path": "2025/225C1529/1FA9A3262B75AB3700FCE3E5BA63E17F9132DB7E4207C2A36A2C3FE8A2AC1E10.pdf", "accessible": true, "nom_fichier": "225C152902.pdf"}, {"path": "2025/225C1529/CAD9D5AA00E77FBFDDA7684EC74AC77B7D3959C40DCD97D54CD5F3DE56F23C42.pdf", "accessible": true, "nom_fichier": "225C152903.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-11-28T11:32:03.293098+01:00", "types_information": ["OPA"]}	2026-05-13 19:17:57.769374+00
38	38	2026-05-13 19:17:58.855578+00	filing_amf	BDIF note d'information OPR — visée: TRONIC'S MICROSYSTEMS S.A. (numero 225C1507)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1507/E301EE3EF6B37DFAD4272EF1E160CA1E5832EADBF8D9B6387733A97822810066.pdf	{"numero": "225C1507", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005911", "raison_sociale": "TRONIC'S MICROSYSTEMS S.A."}, {"role": "Initiateur", "jeton": "RS00007557", "raison_sociale": "TDK ELECTRONICS AG"}], "documents": [{"path": "2025/225C1507/E301EE3EF6B37DFAD4272EF1E160CA1E5832EADBF8D9B6387733A97822810066.pdf", "accessible": true, "nom_fichier": "225C1507.pdf"}, {"path": "2025/225C1507/9F5562E73A80495BAE992A185180EB5D338684DE273ACA29E4BAE3379A8B2E4D.pdf", "accessible": true, "nom_fichier": "225C150700.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-09-09T15:36:20.948578+02:00", "types_information": ["OPA"]}	2026-05-13 19:17:58.85417+00
40	40	2026-05-13 19:18:01.126378+00	filing_amf	BDIF note d'information OPAS — visée: AGROGENERATION (numero 225C1404)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1404/E8EEC4E35E2DEFE94F731224C1A87EB6BB09862E30C84AA012002CD5C640C19B.pdf	{"numero": "225C1404", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005064", "raison_sociale": "AGROGENERATION"}], "documents": [{"path": "2025/225C1404/E8EEC4E35E2DEFE94F731224C1A87EB6BB09862E30C84AA012002CD5C640C19B.pdf", "accessible": true, "nom_fichier": "225C1404.pdf"}, {"path": "2025/225C1404/FF475C89C4EF2B6657A1EFDC639A2958300AB7A4670E9F0D2CC903E813EB9139.pdf", "accessible": true, "nom_fichier": "225C140400.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-08-18T17:14:04.021013+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:01.124906+00
41	41	2026-05-13 19:18:02.201208+00	filing_amf	BDIF note d'information OPAS — visée: AMPLITUDE SURGICAL (numero 225C1285)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1285/AC0DAB36744D4ABF9AB5BE55149059EBF6F4932616FDD31223CFA13D250D0E81.pdf	{"numero": "225C1285", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006019", "raison_sociale": "AMPLITUDE SURGICAL"}], "documents": [{"path": "2025/225C1285/AC0DAB36744D4ABF9AB5BE55149059EBF6F4932616FDD31223CFA13D250D0E81.pdf", "accessible": true, "nom_fichier": "225C1285.pdf"}, {"path": "2025/225C1285/4FDBE555DD6B627143F3DDCA2CBD3B3322BDFAD74F8A791EF4B7768540E85FC4.pdf", "accessible": true, "nom_fichier": "225C128500.pdf"}, {"path": "2025/225C1285/F25581C26A1F520DAA34DF38EB1234658D072A480590704DF71D05FE292DDAA8.pdf", "accessible": true, "nom_fichier": "225C128501.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-07-30T16:46:03.735319+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:02.199776+00
42	42	2026-05-13 19:18:03.179341+00	filing_amf	BDIF note d'information OPA — visée: VOGO (numero 225C1258)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1258/66D00BC0E7AD03BD0F4A7BA4651F295DA8870150DFAB9075D707785B11973CF9.pdf	{"numero": "225C1258", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006663", "raison_sociale": "VOGO"}, {"role": "Initiateur", "jeton": "RS00006263", "raison_sociale": "ABEO"}], "documents": [{"path": "2025/225C1258/66D00BC0E7AD03BD0F4A7BA4651F295DA8870150DFAB9075D707785B11973CF9.pdf", "accessible": true, "nom_fichier": "225C1258.pdf"}, {"path": "2025/225C1258/424B9DFE7AE5E9309CEE3E45125B3BD4D47C5E996D662FE7D224C86535EA1A66.pdf", "accessible": true, "nom_fichier": "225C125800.pdf"}, {"path": "2025/225C1258/20C8F5D5003DDA42A6DBA8AD32942C4F968AF796797E495342354C5A9C23D7E6.pdf", "accessible": true, "nom_fichier": "225C125801.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPA", "OPE"], "date_information": null, "date_publication": "2025-11-28T12:28:03.109387+01:00", "types_information": ["OPA"]}	2026-05-13 19:18:03.177981+00
43	43	2026-05-13 19:18:04.39238+00	filing_amf	BDIF note d'information OPR — visée: GROUPE ETPO SA (numero 225C1227)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1227/8E52F125753476B79E285A529935605690E7CDC62F9935FF2126E850B7197FCA.pdf	{"numero": "225C1227", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00002101", "raison_sociale": "GROUPE ETPO SA"}, {"role": "Initiateur", "jeton": "RS00008064", "raison_sociale": "GROUPE SPIE BATIGNOLLES SAS"}], "documents": [{"path": "2025/225C1227/8E52F125753476B79E285A529935605690E7CDC62F9935FF2126E850B7197FCA.pdf", "accessible": true, "nom_fichier": "225C1227.pdf"}, {"path": "2025/225C1227/8042DA8C637431EB95D96C207BB9EB700E0179FC3E31BB6127997C41D001FBD5.pdf", "accessible": true, "nom_fichier": "225C122700.pdf"}, {"path": "2025/225C1227/E6EF3DF74139612781966FAD438F2190D9E282AA5A8DAF28E542E50C4A4B0773.pdf", "accessible": true, "nom_fichier": "225C122701.pdf"}, {"path": "2025/225C1227/125FED29977988BD31C36373FA0A4AD816D2ABB3DE8621AC1E6128C9C0C84973.pdf", "accessible": true, "nom_fichier": "225C122702.pdf"}, {"path": "2025/225C1227/6F31BC30FA7608954C4261F86D30C8782DDC49D077B0B90C9C4640326011B048.pdf", "accessible": true, "nom_fichier": "225C122703.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-07-18T10:07:18.730585+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:04.390819+00
44	44	2026-05-13 19:18:05.435773+00	filing_amf	BDIF note d'information OPAS — visée: ALTAMIR (numero 225C1154)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1154/C9793687BB098BD663033E6439917178912A6215D9BCE88CC89765EDA50536D9.pdf	{"numero": "225C1154", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003545", "raison_sociale": "ALTAMIR"}, {"role": "Initiateur", "jeton": "RS00005821", "raison_sociale": "AMBOISE SAS"}], "documents": [{"path": "2025/225C1154/C9793687BB098BD663033E6439917178912A6215D9BCE88CC89765EDA50536D9.pdf", "accessible": true, "nom_fichier": "225C1154.pdf"}, {"path": "2025/225C1154/78B83AB59379A58AD81907691888A769135F86790C0A7CACB14CEB1FEDCF39EF.pdf", "accessible": true, "nom_fichier": "225C115400.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-07-04T17:52:04.231798+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:05.434079+00
45	45	2026-05-13 19:18:06.605933+00	filing_amf	BDIF note d'information OPR — visée: BELIEVE (numero 225C1153)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1153/8D4F4D57519FB0DBC66686235B1CC114E7A7C3F0DF2FC2535D4ADE7E847BCC04.pdf	{"numero": "225C1153", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007301", "raison_sociale": "BELIEVE"}], "documents": [{"path": "2025/225C1153/8D4F4D57519FB0DBC66686235B1CC114E7A7C3F0DF2FC2535D4ADE7E847BCC04.pdf", "accessible": true, "nom_fichier": "225C1153.pdf"}, {"path": "2025/225C1153/3ED1679B0A6EA5D247FA2F2950180AA3ACA33D96D66C0EE9FFD1F9462BB3CA07.pdf", "accessible": true, "nom_fichier": "225C115300.pdf"}, {"path": "2025/225C1153/1AF02602AF5AB984039B07DC6514C0F78EC58FFEB54DD80F306575B6B92E6608.pdf", "accessible": true, "nom_fichier": "225C115301.pdf"}, {"path": "2025/225C1153/694AD3BFD466A9B681DB2C5CF1FA9B3351D16CF9CF832B533ADE306ADC2369AB.pdf", "accessible": true, "nom_fichier": "225C115302.pdf"}, {"path": "2025/225C1153/B044F3334D4CE752FC67228BF3E91482985A3C54E3BF523CDD8ACC22D8EFE043.pdf", "accessible": true, "nom_fichier": "225C115303.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-11-28T11:38:03.078680+01:00", "types_information": ["OPA"]}	2026-05-13 19:18:06.603947+00
46	46	2026-05-13 19:18:07.632471+00	filing_amf	BDIF note d'information OPA — visée: ELECTRICITE ET EAUX DE MADAGASCAR (numero 225C1139)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1139/8BBACCFF5CC17C6941B15D31D95987856AAB9CD9E5EFEC4199D8BFA0098A9D2B.pdf	{"numero": "225C1139", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001534", "raison_sociale": "ELECTRICITE ET EAUX DE MADAGASCAR"}], "documents": [{"path": "2025/225C1139/8BBACCFF5CC17C6941B15D31D95987856AAB9CD9E5EFEC4199D8BFA0098A9D2B.pdf", "accessible": true, "nom_fichier": "225C1139.pdf"}, {"path": "2025/225C1139/C0694040C429B8DF5B1C6549928280D1D38B541B9705A109CE010086EECF96A1.pdf", "accessible": true, "nom_fichier": "225C113900.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2025-07-02T11:04:03.578190+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:07.630994+00
47	47	2026-05-13 19:18:08.776081+00	filing_amf	BDIF note d'information OPAS — visée: ALTAMIR (numero 225C1003)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1003/05ABE9DBA29A5ECF05C9F78B5AE905C73FB41BD48C6980F685BFE28737829D77.pdf	{"numero": "225C1003", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003545", "raison_sociale": "ALTAMIR"}, {"role": "Initiateur", "jeton": "RS00005821", "raison_sociale": "AMBOISE SAS"}], "documents": [{"path": "2025/225C1003/05ABE9DBA29A5ECF05C9F78B5AE905C73FB41BD48C6980F685BFE28737829D77.pdf", "accessible": true, "nom_fichier": "225C1003.pdf"}, {"path": "2025/225C1003/53D791546DD15265ABC89869A87CE27A97A0EF8D7113FC5225C3D83BF3C72331.pdf", "accessible": true, "nom_fichier": "225C100300.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-06-16T15:42:05.395383+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:08.774503+00
48	48	2026-05-13 19:18:09.843602+00	filing_amf	BDIF note d'information OPR — visée: GROUPE ETPO SA (numero 225C0995)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0995/89F80B88B4C39CB8BE6C6E00CE15DED65CC13580E802F7616A1FF8EB217C8E76.pdf	{"numero": "225C0995", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00002101", "raison_sociale": "GROUPE ETPO SA"}, {"role": "Initiateur", "jeton": "RS00008064", "raison_sociale": "GROUPE SPIE BATIGNOLLES SAS"}], "documents": [{"path": "2025/225C0995/89F80B88B4C39CB8BE6C6E00CE15DED65CC13580E802F7616A1FF8EB217C8E76.pdf", "accessible": true, "nom_fichier": "225C0995.pdf"}, {"path": "2025/225C0995/AC9F86D9390B2AA59824F202368DB8AECE93A45B9C64B39793B08D84E3DD485D.pdf", "accessible": true, "nom_fichier": "225C099500.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-06-13T15:28:04.083681+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:09.842221+00
49	49	2026-05-13 19:18:11.071688+00	filing_amf	BDIF note d'information OPR — visée: TARKETT S.A. (numero 225C0943)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0943/2766C94AB6689E31301176B6AB33C47F5BFA24283DFC719261629B63E795CE80.pdf	{"numero": "225C0943", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00004395", "raison_sociale": "TARKETT S.A."}], "documents": [{"path": "2025/225C0943/2766C94AB6689E31301176B6AB33C47F5BFA24283DFC719261629B63E795CE80.pdf", "accessible": true, "nom_fichier": "225C0943.pdf"}, {"path": "2025/225C0943/A96918B9C43BE9E169D6B1BB1E62EFCFDE70771790C1AAEAB3207A680546B42D.pdf", "accessible": true, "nom_fichier": "225C094300.pdf"}, {"path": "2025/225C0943/0FD740DCAE6A1568FC8DC71B5EB798191C3FE214F8207C5B28FBE2EB886352F6.pdf", "accessible": true, "nom_fichier": "225C094301.pdf"}, {"path": "2025/225C0943/A17F47C435C3B70922F23388E97C10FC5B2212F224115255783D948DFA4CEA62.pdf", "accessible": true, "nom_fichier": "225C094302.pdf"}, {"path": "2025/225C0943/6E0DB6EDA8C13CD8719FDEAD75CD9945A7FA273C011E9A24CB32BFADD428A7ED.pdf", "accessible": true, "nom_fichier": "225C094303.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-06-06T16:04:07.741077+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:11.070175+00
50	50	2026-05-13 19:18:12.105928+00	filing_amf	BDIF note d'information OPA — visée: VERALLIA (numero 225C0929)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0929/F0920AB04DC74434B52DD0FE7CB8BD0D0848FBCA912571968BD0585BAF6E0DA4.pdf	{"numero": "225C0929", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005230", "raison_sociale": "VERALLIA"}], "documents": [{"path": "2025/225C0929/F0920AB04DC74434B52DD0FE7CB8BD0D0848FBCA912571968BD0585BAF6E0DA4.pdf", "accessible": true, "nom_fichier": "225C0929.pdf"}, {"path": "2025/225C0929/26A2E7D07DEEA627D2E00BBA0858F7CE583DEFCAD3DF67355EB6AB7AB4B794CD.pdf", "accessible": true, "nom_fichier": "225C092900.pdf"}, {"path": "2025/225C0929/B58961131B07E92E283A2002B7AF8D73E89E6178FBEBAA0FC8674C3FDB10EBA7.pdf", "accessible": true, "nom_fichier": "225C092901.pdf"}, {"path": "2025/225C0929/997345C48EA356E175468B3164D21C409DD0521E37166BF49F2AE18D5F96D5ED.pdf", "accessible": true, "nom_fichier": "225C092902.pdf"}, {"path": "2025/225C0929/284AF5354134531A49E4B17B84A7DC4607604F21A0F239424F9E6B2A7617D39D.pdf", "accessible": true, "nom_fichier": "225C092903.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2025-11-28T11:50:03.414641+01:00", "types_information": ["OPA"]}	2026-05-13 19:18:12.104232+00
51	51	2026-05-13 19:18:14.159922+00	filing_amf	BDIF note d'information OPAS — visée: M2I (numero 225C0921)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0921/598AEEE4C8C8BA22E6E8F10899BF9587CAB180EDE7FD1370A2FC31000A928867.pdf	{"numero": "225C0921", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006453", "raison_sociale": "M2I"}, {"role": "Initiateur", "jeton": "RS00008346", "raison_sociale": "ABILWAYS"}], "documents": [{"path": "2025/225C0921/598AEEE4C8C8BA22E6E8F10899BF9587CAB180EDE7FD1370A2FC31000A928867.pdf", "accessible": true, "nom_fichier": "225C0921.pdf"}, {"path": "2025/225C0921/9A2E08060931AD51C8096901B068490CF7D45DCEB8DAEEE4ADCAA4EBFFD64448.pdf", "accessible": true, "nom_fichier": "225C092100.pdf"}, {"path": "2025/225C0921/3EBE828830F1E7B2B1B84E89783BAC80C99E92BC6161B6EA59B4D021D17DE991.pdf", "accessible": true, "nom_fichier": "225C092101.pdf"}, {"path": "2025/225C0921/3AFB054045C21DAAF7D67BE690879D9F4EFC14A402EB270FDD2DC5D2F8D16634.pdf", "accessible": true, "nom_fichier": "225C092102.pdf"}, {"path": "2025/225C0921/A144ED5AE09E939FBE1193CA3DF91E22B9515A0FDC834BEBEF30F40056754F75.pdf", "accessible": true, "nom_fichier": "225C092103.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-06-06T09:12:04.121903+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:14.158197+00
52	52	2026-05-13 19:18:15.267391+00	filing_amf	BDIF note d'information OPR — visée: BELIEVE (numero 225C0920)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0920/EFA14EF47EA8E982099F77768E6D5DB5982A1FB2DD38ADF653B80696FF46ED09.pdf	{"numero": "225C0920", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007301", "raison_sociale": "BELIEVE"}], "documents": [{"path": "2025/225C0920/EFA14EF47EA8E982099F77768E6D5DB5982A1FB2DD38ADF653B80696FF46ED09.pdf", "accessible": true, "nom_fichier": "225C0920.pdf"}, {"path": "2025/225C0920/687A00EC0F8F9852DB99F931A1DE80A0BDA3602102F747A22FFA6E77CD482376.pdf", "accessible": true, "nom_fichier": "225C092000.pdf"}, {"path": "2025/225C0920/D02284CB5882C6EAE8C10B5FB47B6C7691F3E0FAEFEAA26964E152CAC1D8A93B.pdf", "accessible": true, "nom_fichier": "225C092001.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-06-05T15:12:03.404049+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:15.265624+00
53	53	2026-05-13 19:18:16.351583+00	filing_amf	BDIF note d'information OPAS — visée: UNIBEL (numero 225C0845)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0845/5959CDC36EEA75D9BB16F9817DF6C7314CE63D89790E33FEB1DA8C70DFF12CC7.pdf	{"numero": "225C0845", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001324", "raison_sociale": "UNIBEL"}], "documents": [{"path": "2025/225C0845/5959CDC36EEA75D9BB16F9817DF6C7314CE63D89790E33FEB1DA8C70DFF12CC7.pdf", "accessible": true, "nom_fichier": "225C0845.pdf"}, {"path": "2025/225C0845/F6B854E2EA4C8114C16C06AF44CBC94EE58E8DB8EC650DBB2A5638BFDD24E0F2.pdf", "accessible": true, "nom_fichier": "225C084500.pdf"}, {"path": "2025/225C0845/F606865ACB00FE0E6CC31A002E6E0599B5B46907911CE7A6F657E227DC6CA32A.pdf", "accessible": true, "nom_fichier": "225C084501.pdf"}, {"path": "2025/225C0845/DDD1B0FCE9002020B519FCE22F7F36596C2760DD6CE0C7DC71819327BF24388F.pdf", "accessible": true, "nom_fichier": "225C084502.pdf"}, {"path": "2025/225C0845/328E75E90EE85D78DC84BDFDD3316A7568D85112FE531D756987E9E454AEBA4A.pdf", "accessible": true, "nom_fichier": "225C084503.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-05-26T10:50:04.815369+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:16.349676+00
54	54	2026-05-13 19:18:17.357135+00	filing_amf	BDIF note d'information OPR — visée: GROUPE ETPO SA (numero 225C0838)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0838/7C5773E08924691DD74132E2C661DB3DE388B66A8E0BB41F5FADB7D71B0D3202.pdf	{"numero": "225C0838", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00002101", "raison_sociale": "GROUPE ETPO SA"}, {"role": "Initiateur", "jeton": "RS00008064", "raison_sociale": "GROUPE SPIE BATIGNOLLES SAS"}], "documents": [{"path": "2025/225C0838/7C5773E08924691DD74132E2C661DB3DE388B66A8E0BB41F5FADB7D71B0D3202.pdf", "accessible": true, "nom_fichier": "225C0838.pdf"}, {"path": "2025/225C0838/8CC64886C10A163C01A011243CC8F371C7001F252AEDBC6CBA572A45A9D50B19.pdf", "accessible": true, "nom_fichier": "225C083800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-05-22T16:20:03.796535+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:17.355813+00
55	55	2026-05-13 19:18:18.493642+00	filing_amf	BDIF note d'information OPR — visée: FINANCIERE MONCEY (numero 225C0741)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0741/17E366B209E9E2ED0180EB9A7C7B00839735621223DF35947F824CB4EFE1E12D.pdf	{"numero": "225C0741", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001419", "raison_sociale": "FINANCIERE MONCEY"}, {"role": "Initiateur", "jeton": "RS00000987", "raison_sociale": "BOLLORE SE"}], "documents": [{"path": "2025/225C0741/17E366B209E9E2ED0180EB9A7C7B00839735621223DF35947F824CB4EFE1E12D.pdf", "accessible": true, "nom_fichier": "225C0741.pdf"}, {"path": "2025/225C0741/2EE87FB9C753D96753E1E5FBFBF1BEBF1FDA154F5879945E1D6191ABD4E56C58.pdf", "accessible": true, "nom_fichier": "225C074100.pdf"}, {"path": "2025/225C0741/6869504BF61AE54B120F517D53241E8CDAD3045EE1FFEA9968BA9D62E2979B45.pdf", "accessible": true, "nom_fichier": "225C074101.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-05-05T09:32:07.811169+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:18.492276+00
56	56	2026-05-13 19:18:19.62581+00	filing_amf	BDIF note d'information OPR — visée: COMPAGNIE DU CAMBODGE (numero 225C0740)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0740/1283751425D68B1A5DF96C9EC10E51976B0C0CEE68842E85A9393EC463C78975.pdf	{"numero": "225C0740", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001364", "raison_sociale": "COMPAGNIE DU CAMBODGE"}, {"role": "Initiateur", "jeton": "RS00000987", "raison_sociale": "BOLLORE SE"}], "documents": [{"path": "2025/225C0740/1283751425D68B1A5DF96C9EC10E51976B0C0CEE68842E85A9393EC463C78975.pdf", "accessible": true, "nom_fichier": "225C0740.pdf"}, {"path": "2025/225C0740/AB74D7B64C0197ED4E43418DB1B0D6B01AD6BA3D706C639B918DB194D1361450.pdf", "accessible": true, "nom_fichier": "225C074000.pdf"}, {"path": "2025/225C0740/98698EC392BD475B7E05463B440106A8368629668EA7F709BBEE7D2CFB85582B.pdf", "accessible": true, "nom_fichier": "225C074001.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-05-05T09:32:12.046088+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:19.624256+00
57	57	2026-05-13 19:18:20.742112+00	filing_amf	BDIF note d'information OPR — visée: SOCIETE INDUSTRIELLE ET FINANCIERE DE L'ARTOIS (numero 225C0739)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0739/49EDABB0E59E6DFB2185881C48662DD85049EDD259627F0F16D69C6A9FFDF6A4.pdf	{"numero": "225C0739", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001429", "raison_sociale": "SOCIETE INDUSTRIELLE ET FINANCIERE DE L'ARTOIS"}, {"role": "Initiateur", "jeton": "RS00000987", "raison_sociale": "BOLLORE SE"}], "documents": [{"path": "2025/225C0739/49EDABB0E59E6DFB2185881C48662DD85049EDD259627F0F16D69C6A9FFDF6A4.pdf", "accessible": true, "nom_fichier": "225C0739.pdf"}, {"path": "2025/225C0739/8B2B361D2CF00AFDA16A3C28FB55CCE62510D5CA25EA189E000EF5699B236CFF.pdf", "accessible": true, "nom_fichier": "225C073900.pdf"}, {"path": "2025/225C0739/5B0E9A92DCD0FD263A1107C111635A9B66CDCF6F335FB571434675A6A3954278.pdf", "accessible": true, "nom_fichier": "225C073901.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-11-28T11:14:03.282481+01:00", "types_information": ["OPA"]}	2026-05-13 19:18:20.740774+00
58	58	2026-05-13 19:18:21.897344+00	filing_amf	BDIF note d'information OPAS — visée: M2I (numero 225C0725)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0725/686E4EA41EA6F49A0DDF69C4D06BBD4A0CE2D1FB6D7F3A165F8BB9E22B2AABE2.pdf	{"numero": "225C0725", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006453", "raison_sociale": "M2I"}, {"role": "Initiateur", "jeton": "RS00008346", "raison_sociale": "ABILWAYS"}], "documents": [{"path": "2025/225C0725/686E4EA41EA6F49A0DDF69C4D06BBD4A0CE2D1FB6D7F3A165F8BB9E22B2AABE2.pdf", "accessible": true, "nom_fichier": "225C0725.pdf"}, {"path": "2025/225C0725/3BEA91AF05563A7F56958790A25463A0FCE8E01359027F1FD30567D1FD733686.pdf", "accessible": true, "nom_fichier": "225C072500.pdf"}, {"path": "2025/225C0725/20ED108DC53F2BF18B3EBF98634106DE5C22EF6B7575DCE2FADBBED2B8BEF5E8.pdf", "accessible": true, "nom_fichier": "225C072501.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-06-06T09:14:04.011659+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:21.895918+00
59	59	2026-05-13 19:18:22.903765+00	filing_amf	BDIF note d'information OPA — visée: VERALLIA (numero 225C0708)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0708/307129575A270937D25873228E87EF688B894D56B00E9385B4121A76FCC35177.pdf	{"numero": "225C0708", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005230", "raison_sociale": "VERALLIA"}], "documents": [{"path": "2025/225C0708/307129575A270937D25873228E87EF688B894D56B00E9385B4121A76FCC35177.pdf", "accessible": true, "nom_fichier": "225C0708.pdf"}, {"path": "2025/225C0708/ACF88250E68514815796696D415A08F8E6D3302AC518A231BEB4802BDC8CDC20.pdf", "accessible": true, "nom_fichier": "225C070800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2025-06-06T08:40:04.095319+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:22.902183+00
60	60	2026-05-13 19:18:23.9717+00	filing_amf	BDIF note d'information OPR — visée: TARKETT S.A. (numero 225C0697)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0697/52E5D27DF0828B074AB7125AB17D808DC90C8DEEF08C87960D271D8CA892BFC6.pdf	{"numero": "225C0697", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00004395", "raison_sociale": "TARKETT S.A."}], "documents": [{"path": "2025/225C0697/52E5D27DF0828B074AB7125AB17D808DC90C8DEEF08C87960D271D8CA892BFC6.pdf", "accessible": true, "nom_fichier": "225C0697.pdf"}, {"path": "2025/225C0697/6BA522FE0A184E88DB1DB52AC0DF88A31E05B89D26C560D0EECDAC6835403934.pdf", "accessible": true, "nom_fichier": "225C069700.pdf"}, {"path": "2025/225C0697/6ECC13E22333A4492FD6FAE768AF3A630105BD8BFB1555A6D84C47F507520CF1.pdf", "accessible": true, "nom_fichier": "225C069701.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-04-24T16:26:03.794311+02:00", "types_information": ["OPA"]}	2026-05-13 19:18:23.970107+00
\.


--
-- Data for Name: paper_positions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.paper_positions (id, deal_id, open_ts, close_ts, entry_price, exit_price, size_eur, side, pnl_eur, status, notes) FROM stdin;
\.


--
-- Data for Name: prices; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.prices (ticker, ts, open, high, low, close, volume, source) FROM stdin;
\.


--
-- Data for Name: scores; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.scores (id, deal_id, ts, p_completion, p_market_implied, edge, expected_return_annualized, decision, model_version, features) FROM stdin;
\.


--
-- Name: bgw_job_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: -
--

SELECT pg_catalog.setval('_timescaledb_catalog.bgw_job_id_seq', 1001, true);


--
-- Name: chunk_column_stats_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: -
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_column_stats_id_seq', 1, false);


--
-- Name: chunk_constraint_name; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: -
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_constraint_name', 1, false);


--
-- Name: chunk_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: -
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_id_seq', 1, false);


--
-- Name: dimension_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: -
--

SELECT pg_catalog.setval('_timescaledb_catalog.dimension_id_seq', 3, true);


--
-- Name: dimension_slice_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: -
--

SELECT pg_catalog.setval('_timescaledb_catalog.dimension_slice_id_seq', 1, false);


--
-- Name: hypertable_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: -
--

SELECT pg_catalog.setval('_timescaledb_catalog.hypertable_id_seq', 3, true);


--
-- Name: analyses_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.analyses_id_seq', 1, false);


--
-- Name: deals_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.deals_id_seq', 60, true);


--
-- Name: events_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.events_id_seq', 60, true);


--
-- Name: paper_positions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.paper_positions_id_seq', 1, false);


--
-- Name: scores_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.scores_id_seq', 1, false);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: analyses analyses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analyses
    ADD CONSTRAINT analyses_pkey PRIMARY KEY (id);


--
-- Name: deals deals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deals
    ADD CONSTRAINT deals_pkey PRIMARY KEY (id);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: paper_positions paper_positions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_positions
    ADD CONSTRAINT paper_positions_pkey PRIMARY KEY (id);


--
-- Name: prices prices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prices
    ADD CONSTRAINT prices_pkey PRIMARY KEY (ticker, ts);


--
-- Name: scores scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scores
    ADD CONSTRAINT scores_pkey PRIMARY KEY (id);


--
-- Name: deals uq_deals_juridiction_regulator_ref; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deals
    ADD CONSTRAINT uq_deals_juridiction_regulator_ref UNIQUE (juridiction, regulator_ref);


--
-- Name: _materialized_hypertable_2_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_2_bucket_idx ON _timescaledb_internal._materialized_hypertable_2 USING btree (bucket DESC);


--
-- Name: _materialized_hypertable_2_ticker_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_2_ticker_bucket_idx ON _timescaledb_internal._materialized_hypertable_2 USING btree (ticker, bucket DESC);


--
-- Name: _materialized_hypertable_3_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_3_bucket_idx ON _timescaledb_internal._materialized_hypertable_3 USING btree (bucket DESC);


--
-- Name: _materialized_hypertable_3_ticker_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_3_ticker_bucket_idx ON _timescaledb_internal._materialized_hypertable_3 USING btree (ticker, bucket DESC);


--
-- Name: ix_analyses_deal_id_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analyses_deal_id_ts ON public.analyses USING btree (deal_id, ts);


--
-- Name: ix_deals_juridiction_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_deals_juridiction_status ON public.deals USING btree (juridiction, status);


--
-- Name: ix_deals_ticker_target; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_deals_ticker_target ON public.deals USING btree (ticker_target);


--
-- Name: ix_events_deal_id_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_events_deal_id_ts ON public.events USING btree (deal_id, ts);


--
-- Name: ix_events_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_events_event_type ON public.events USING btree (event_type);


--
-- Name: ix_paper_positions_deal_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_paper_positions_deal_id ON public.paper_positions USING btree (deal_id);


--
-- Name: ix_paper_positions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_paper_positions_status ON public.paper_positions USING btree (status);


--
-- Name: ix_prices_ticker_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prices_ticker_ts ON public.prices USING btree (ticker, ts DESC);


--
-- Name: ix_scores_deal_id_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_scores_deal_id_ts ON public.scores USING btree (deal_id, ts);


--
-- Name: prices_ts_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX prices_ts_idx ON public.prices USING btree (ts DESC);


--
-- Name: analyses analyses_deal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analyses
    ADD CONSTRAINT analyses_deal_id_fkey FOREIGN KEY (deal_id) REFERENCES public.deals(id) ON DELETE CASCADE;


--
-- Name: events events_deal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_deal_id_fkey FOREIGN KEY (deal_id) REFERENCES public.deals(id) ON DELETE CASCADE;


--
-- Name: paper_positions paper_positions_deal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_positions
    ADD CONSTRAINT paper_positions_deal_id_fkey FOREIGN KEY (deal_id) REFERENCES public.deals(id) ON DELETE CASCADE;


--
-- Name: scores scores_deal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scores
    ADD CONSTRAINT scores_deal_id_fkey FOREIGN KEY (deal_id) REFERENCES public.deals(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict 4InCuFbmZ3iI4RcodlPnKBnkjNMdgpXgJGWfYPJ2bJfafL5bfRVhAP6k8I6WCYC

