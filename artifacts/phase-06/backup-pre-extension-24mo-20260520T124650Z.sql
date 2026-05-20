--
-- PostgreSQL database dump
--

\restrict BJQWjw5zUTSYxU7ggHmBbsSvB9amYfIYk4FkPelcQnDFanEEo20KGDPcN8C91j3

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
    'erwerbsangebot',
    'delisting_offer',
    'opa_volontaria_preventiva'
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
-- Name: vendor_api_usage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendor_api_usage (
    id bigint NOT NULL,
    vendor character varying(32) NOT NULL,
    year_month character varying(7) NOT NULL,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    request_url text,
    target_url text,
    credits_cost integer NOT NULL,
    http_status integer,
    extra jsonb,
    CONSTRAINT ck_vendor_api_usage_cost_nonneg CHECK ((credits_cost >= 0))
);


--
-- Name: vendor_api_usage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendor_api_usage_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendor_api_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendor_api_usage_id_seq OWNED BY public.vendor_api_usage.id;


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
-- Name: vendor_api_usage id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_api_usage ALTER COLUMN id SET DEFAULT nextval('public.vendor_api_usage_id_seq'::regclass);


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
1	1779274800000000
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
3	-9223372036854775808	1778630399999999
2	-9223372036854775808	1779029999999999
3	1779148800000000	9223372036854775807
2	1779274800000000	9223372036854775807
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
exported_uuid	3c726f41-2b67-4d39-b333-5752fdab2b69	t
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
0007
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
1	FR	226C0683	\N	\N	POULAILLON	[pending parse]	2026-05-18	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0683/AF100678026C5A3376D19A90BA0FE83D523F43E41FDCF886248CF89772F495D6.pdf	/repo/data/pdfs/fr/2026/226C0683.pdf	2026-05-19 14:23:10.781503+00	2026-05-19 14:23:10.781503+00	\N
2	FR	226C0661	\N	\N	MEDIA 6	[pending parse]	2026-05-11	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0661/954781AD2F1F1BF3816AA9C708025BF72D9C54D8CFCF908238AD85B40E413D3B.pdf	/repo/data/pdfs/fr/2026/226C0661.pdf	2026-05-19 14:23:10.845166+00	2026-05-19 14:23:10.845166+00	\N
3	FR	226C0645	\N	\N	MEDIA 6	[pending parse]	2026-05-07	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0645/FE0616923D43D1F060E72056AFCF74F91E1A385883F3C547318A36E8027D6E2E.pdf	/repo/data/pdfs/fr/2026/226C0645.pdf	2026-05-19 14:23:10.884163+00	2026-05-19 14:23:10.884163+00	\N
4	FR	226C0644	\N	\N	FNAC DARTY	[pending parse]	2026-05-12	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0644/72DF20BE22E022A2C30DC6186B5CC3F77B31B85FA0D84EE9D1465AF96DF8A90C.pdf	/repo/data/pdfs/fr/2026/226C0644.pdf	2026-05-19 14:23:10.921401+00	2026-05-19 14:23:10.921401+00	\N
5	FR	226C0620	\N	\N	VINPAI	[pending parse]	2026-05-04	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0620/C88737C27EBA36B4ABE577D1CF942FADDF3FCB9A27BDA639FEA0105D816741C4.pdf	/repo/data/pdfs/fr/2026/226C0620.pdf	2026-05-19 14:23:10.961674+00	2026-05-19 14:23:10.961674+00	\N
6	FR	226C0591	\N	\N	ELECTRICITE ET EAUX DE MADAGASCAR	[pending parse]	2026-04-28	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0591/348695808BFBEBA6FD7244F05D2B43B6FB5C3DDBB70A75CFDDE0145335D82145.pdf	/repo/data/pdfs/fr/2026/226C0591.pdf	2026-05-19 14:23:11.006923+00	2026-05-19 14:23:11.006923+00	\N
7	FR	226C0578	\N	\N	POULAILLON	[pending parse]	2026-04-23	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0578/B956DC68725674FD12F3349D2160F0F214B32A3B47E1E2C948F36C10F05C7C1D.pdf	/repo/data/pdfs/fr/2026/226C0578.pdf	2026-05-19 14:23:11.043373+00	2026-05-19 14:23:11.043373+00	\N
8	FR	226C0550	\N	\N	TERACT	[pending parse]	2026-04-20	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0550/790CEA3A90861D7F49FCC7EC86FDEE425D31E42EEA5597D127F45DCF68783FB8.pdf	/repo/data/pdfs/fr/2026/226C0550.pdf	2026-05-19 14:23:11.079566+00	2026-05-19 14:23:11.079566+00	\N
9	FR	226C0538	\N	\N	SOCIETE DE LA TOUR EIFFEL	[pending parse]	2026-04-17	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0538/F1A0A887F62CDDB65C1D688EA3F99A87CCBF26975A738C848CFAF5EB83C3E9AB.pdf	/repo/data/pdfs/fr/2026/226C0538.pdf	2026-05-19 14:23:11.110069+00	2026-05-19 14:23:11.110069+00	\N
10	FR	226C0531	\N	\N	MEDIA 6	[pending parse]	2026-04-16	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0531/561AA4EE77DE083659474F2355A75F1A1AFA156AD34FED1FC6872CCF0A07CE87.pdf	/repo/data/pdfs/fr/2026/226C0531.pdf	2026-05-19 14:23:11.162304+00	2026-05-19 14:23:11.162304+00	\N
11	FR	226C0511	\N	\N	GAUMONT	[pending parse]	2026-04-13	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0511/AB617FF3C053B29C0869579FC6C94E567E94EF5CA54AD731BEFC90096BF14FB9.pdf	/repo/data/pdfs/fr/2026/226C0511.pdf	2026-05-19 14:23:11.198702+00	2026-05-19 14:23:11.198702+00	\N
12	FR	226C0347	\N	\N	BALYO	[pending parse]	2026-03-19	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0347/0B2F7A8AF7A42A5DB26EAA3C63A63EAEB4397FC23899488D3EE974E2276033AD.pdf	/repo/data/pdfs/fr/2026/226C0347.pdf	2026-05-19 14:23:11.232917+00	2026-05-19 14:23:11.232917+00	\N
13	FR	226C0318	\N	\N	MEDIA 6	[pending parse]	2026-03-16	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0318/2E2150D58F6F479C2C8EF560F6397E1558E9AF7DDB22A89699FC6027C7914D34.pdf	/repo/data/pdfs/fr/2026/226C0318.pdf	2026-05-19 14:23:11.264895+00	2026-05-19 14:23:11.264895+00	\N
14	FR	226C0287	\N	\N	FNAC DARTY	[pending parse]	2026-03-12	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0287/DBE2E400A000FC29A55CD25156BC15A62A7E389B563ED4E91BC02C772EA0F33F.pdf	/repo/data/pdfs/fr/2026/226C0287.pdf	2026-05-19 14:23:11.297026+00	2026-05-19 14:23:11.297026+00	\N
15	FR	226C0278	\N	\N	TERACT	[pending parse]	2026-03-09	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0278/A31DB49A0FE6CB4A382C7B960FF679D3F9018C80059A4C02ECC31EB5E653A6CE.pdf	/repo/data/pdfs/fr/2026/226C0278.pdf	2026-05-19 14:23:11.334742+00	2026-05-19 14:23:11.334742+00	\N
16	FR	226C0210	\N	\N	GROUPE TERA	[pending parse]	2026-02-19	opra	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0210/1C1F1BF8B08724AE8CC9283B6501A90015C258F03837A071E732589AE12E82E0.pdf	/repo/data/pdfs/fr/2026/226C0210.pdf	2026-05-19 14:23:11.548622+00	2026-05-19 14:23:11.548622+00	\N
17	FR	226C0157	\N	\N	TERACT	[pending parse]	2026-02-05	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0157/2954E3860C1959ADF0F7724A2D2E9CF1D89B305D888D3417CE3DF95E46E1D798.pdf	/repo/data/pdfs/fr/2026/226C0157.pdf	2026-05-19 14:23:11.624764+00	2026-05-19 14:23:11.624764+00	\N
18	FR	226C0156	\N	\N	UV GERMI	[pending parse]	2026-02-05	opra	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0156/66D132B49FB29CB455C97C16A2949728C4D3153D4E3A35EF0F7E7B5E8B9D09CD.pdf	/repo/data/pdfs/fr/2026/226C0156.pdf	2026-05-19 14:23:11.664168+00	2026-05-19 14:23:11.664168+00	\N
19	FR	226C0095	\N	\N	SOCIETE DE TAYNINH	[pending parse]	2026-01-23	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0095/69C403AC9DB64955C7CF92305B5B134E2AD8BE64C70A33B64DE758B67E616C68.pdf	/repo/data/pdfs/fr/2026/226C0095.pdf	2026-05-19 14:23:11.690654+00	2026-05-19 14:23:11.690654+00	\N
20	FR	226C0020	\N	\N	BALYO	[pending parse]	2026-01-07	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0020/DFF429DF18AF43BC18E7971ABF71A2F5B90B0255B4EBB18EB268F6D1579C2074.pdf	/repo/data/pdfs/fr/2026/226C0020.pdf	2026-05-19 14:23:11.719628+00	2026-05-19 14:23:11.719628+00	\N
21	FR	226C0008	\N	\N	GROUPE TERA	[pending parse]	2026-01-05	opra	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0008/CFFC2BF9EC93BB0D5C735AC1596CCD7BAE08ACB2F02F38BE5E387266621C223E.pdf	/repo/data/pdfs/fr/2026/226C0008.pdf	2026-05-19 14:23:11.750639+00	2026-05-19 14:23:11.750639+00	\N
22	FR	225C2156	\N	\N	PRODWARE	PHAST INVEST	2026-01-23	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2156/ADFDAA0E32B9156501354BF7041F099EE4B743B76ED64C90DE8EB363A1ABCD88.pdf	/repo/data/pdfs/fr/2026/225C2156.pdf	2026-05-19 14:23:11.788603+00	2026-05-19 14:23:11.788603+00	\N
23	FR	225C2136	\N	\N	UV GERMI	[pending parse]	2025-12-16	opra	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2136/B94BBB38882DB1DDE9148BF8D7FD9AF90D3A1681299822A01FC9104155FA4E48.pdf	/repo/data/pdfs/fr/2025/225C2136.pdf	2026-05-19 14:23:11.825417+00	2026-05-19 14:23:11.825417+00	\N
24	FR	225C2135	\N	\N	ELECTRICITE ET EAUX DE MADAGASCAR	[pending parse]	2025-12-17	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2135/5C51631DA1F169C7D81C593980694A6CCD25AE6C6A562F86302C14EDCD2F0C92.pdf	/repo/data/pdfs/fr/2025/225C2135.pdf	2026-05-19 14:23:11.856788+00	2026-05-19 14:23:11.856788+00	\N
25	FR	225C2081	\N	\N	SOCIETE DE TAYNINH	[pending parse]	2025-12-08	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2081/8CC4832C7F06C4C44A2C8A3798DA63476B655465D14B3460FE2B3DE3C7020FD0.pdf	/repo/data/pdfs/fr/2025/225C2081.pdf	2026-05-19 14:23:11.886867+00	2026-05-19 14:23:11.886867+00	\N
26	FR	225C2063	\N	\N	BALYO	[pending parse]	2026-01-22	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2063/4B74E67D96D0415272C70A7A4D4DC3BBE94E2C570A5E4BFFDAB4B0F44776363F.pdf	/repo/data/pdfs/fr/2026/225C2063.pdf	2026-05-19 14:23:11.911954+00	2026-05-19 14:23:11.911954+00	\N
27	FR	225C2061	\N	\N	COGELEC	[pending parse]	2026-01-22	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2061/1BE71CDDD093C59BF3C0816994D45C9364CA1D5E1088325B1A6E64CC57C7F564.pdf	/repo/data/pdfs/fr/2026/225C2061.pdf	2026-05-19 14:23:11.939552+00	2026-05-19 14:23:11.939552+00	\N
28	FR	225C1971	\N	\N	WAGA ENERGY	[pending parse]	2025-11-24	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1971/1561FA645F4D0517BB7B8C3D54435902C7D730202735D1145A8BF8C250D66A3C.pdf	/repo/data/pdfs/fr/2025/225C1971.pdf	2026-05-19 14:23:11.966245+00	2026-05-19 14:23:11.966245+00	\N
29	FR	225C1924	\N	\N	PRODWARE	PHAST INVEST	2025-11-14	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1924/278CEE170D11B4B719A5AF39E6EF5D5D98777BCB414E8E0447C8A4C43B17A99C.pdf	/repo/data/pdfs/fr/2025/225C1924.pdf	2026-05-19 14:23:11.991873+00	2026-05-19 14:23:11.991873+00	\N
30	FR	225C1884	\N	\N	TRONIC'S MICROSYSTEMS S.A.	TDK ELECTRONICS AG	2025-11-13	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1884/B2E25865C4580D8F7E0BAA669B6652F2AF700806DAAE34F81EBEE76DC60766A8.pdf	/repo/data/pdfs/fr/2025/225C1884.pdf	2026-05-19 14:23:12.020703+00	2026-05-19 14:23:12.020703+00	\N
31	FR	225C1797	\N	\N	PRODWARE	PHAST INVEST	2025-10-24	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1797/18E0F87ABC999B41EECECC8FE71915ACAC89A921DE6C878FBDFA509EEE420DDE.pdf	/repo/data/pdfs/fr/2025/225C1797.pdf	2026-05-19 14:23:12.044928+00	2026-05-19 14:23:12.044928+00	\N
32	FR	225C1794	\N	\N	VOGO	ABEO	2025-11-28	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1794/46A8BC8D13F4BFEE1C3F6C7EA75130F3F12717FB75CF6FF6F406DE51A430F10E.pdf	/repo/data/pdfs/fr/2025/225C1794.pdf	2026-05-19 14:23:12.072308+00	2026-05-19 14:23:12.072308+00	\N
33	FR	225C1755	\N	\N	COGELEC	[pending parse]	2025-10-15	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1755/AA36F6148357F70B3CEA5A545CC6F7C5082938EC4B57FCFF4588A719CA34AB0D.pdf	/repo/data/pdfs/fr/2025/225C1755.pdf	2026-05-19 14:23:12.098073+00	2026-05-19 14:23:12.098073+00	\N
34	FR	225C1734	\N	\N	AGROGENERATION	[pending parse]	2025-10-13	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1734/B3BE65DA8A38EFEF0C6E0B463784BE812AFE929914A3F3416AE80A2CF9A7818E.pdf	/repo/data/pdfs/fr/2025/225C1734.pdf	2026-05-19 14:23:12.127561+00	2026-05-19 14:23:12.127561+00	\N
35	FR	225C1666	\N	\N	WAGA ENERGY	[pending parse]	2025-10-02	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1666/A2460CAD381A8AA7A5E0566E2B02915BD2C21EB7F7F41119354BA67BBCF0C01E.pdf	/repo/data/pdfs/fr/2025/225C1666.pdf	2026-05-19 14:23:12.155166+00	2026-05-19 14:23:12.155166+00	\N
36	FR	225C1665	\N	\N	TRONIC'S MICROSYSTEMS S.A.	TDK ELECTRONICS AG	2025-10-01	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1665/4BCBC4A976AD1A11A4CFC01F982000092C433608C9B947BF53BA5D350947542F.pdf	/repo/data/pdfs/fr/2025/225C1665.pdf	2026-05-19 14:23:12.183876+00	2026-05-19 14:23:12.183876+00	\N
37	FR	225C1629	\N	\N	AMPLITUDE SURGICAL	[pending parse]	2025-11-28	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1629/8DF9E6C891A17EFCBB495FC63F9C7982DA9D8429C2BCBDA248C9DD77B85D97C3.pdf	/repo/data/pdfs/fr/2025/225C1629.pdf	2026-05-19 14:23:12.209835+00	2026-05-19 14:23:12.209835+00	\N
38	FR	225C1529	\N	\N	ALTAMIR	AMBOISE SAS	2025-11-28	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1529/B5E5B14DB09B63248AD314DE0677266181D86CE9711A330BBDDE64135A76DED8.pdf	/repo/data/pdfs/fr/2025/225C1529.pdf	2026-05-19 14:23:12.23636+00	2026-05-19 14:23:12.23636+00	\N
39	FR	225C1507	\N	\N	TRONIC'S MICROSYSTEMS S.A.	TDK ELECTRONICS AG	2025-09-09	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1507/E301EE3EF6B37DFAD4272EF1E160CA1E5832EADBF8D9B6387733A97822810066.pdf	/repo/data/pdfs/fr/2025/225C1507.pdf	2026-05-19 14:23:12.267021+00	2026-05-19 14:23:12.267021+00	\N
40	FR	225C1439	\N	\N	AGROGENERATION	[pending parse]	2025-08-26	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1439/24F7E7C9EB30188B5FD0914078F16AB748E20D5EE7649132863B135FE4017D31.pdf	/repo/data/pdfs/fr/2025/225C1439.pdf	2026-05-19 14:23:12.294252+00	2026-05-19 14:23:12.294252+00	\N
41	FR	225C1404	\N	\N	AGROGENERATION	[pending parse]	2025-08-18	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1404/E8EEC4E35E2DEFE94F731224C1A87EB6BB09862E30C84AA012002CD5C640C19B.pdf	/repo/data/pdfs/fr/2025/225C1404.pdf	2026-05-19 14:23:12.321864+00	2026-05-19 14:23:12.321864+00	\N
42	FR	225C1285	\N	\N	AMPLITUDE SURGICAL	[pending parse]	2025-07-30	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1285/AC0DAB36744D4ABF9AB5BE55149059EBF6F4932616FDD31223CFA13D250D0E81.pdf	/repo/data/pdfs/fr/2025/225C1285.pdf	2026-05-19 14:23:12.354277+00	2026-05-19 14:23:12.354277+00	\N
43	FR	225C1258	\N	\N	VOGO	ABEO	2025-11-28	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1258/66D00BC0E7AD03BD0F4A7BA4651F295DA8870150DFAB9075D707785B11973CF9.pdf	/repo/data/pdfs/fr/2025/225C1258.pdf	2026-05-19 14:23:12.3765+00	2026-05-19 14:23:12.3765+00	\N
44	FR	225C1227	\N	\N	GROUPE ETPO SA	GROUPE SPIE BATIGNOLLES SAS	2025-07-18	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1227/8E52F125753476B79E285A529935605690E7CDC62F9935FF2126E850B7197FCA.pdf	/repo/data/pdfs/fr/2025/225C1227.pdf	2026-05-19 14:23:12.398899+00	2026-05-19 14:23:12.398899+00	\N
45	FR	225C1154	\N	\N	ALTAMIR	AMBOISE SAS	2025-07-04	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1154/C9793687BB098BD663033E6439917178912A6215D9BCE88CC89765EDA50536D9.pdf	/repo/data/pdfs/fr/2025/225C1154.pdf	2026-05-19 14:23:12.42513+00	2026-05-19 14:23:12.42513+00	\N
46	FR	225C1153	\N	\N	BELIEVE	[pending parse]	2025-11-28	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1153/8D4F4D57519FB0DBC66686235B1CC114E7A7C3F0DF2FC2535D4ADE7E847BCC04.pdf	/repo/data/pdfs/fr/2025/225C1153.pdf	2026-05-19 14:23:12.451583+00	2026-05-19 14:23:12.451583+00	\N
47	FR	225C1139	\N	\N	ELECTRICITE ET EAUX DE MADAGASCAR	[pending parse]	2025-07-02	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1139/8BBACCFF5CC17C6941B15D31D95987856AAB9CD9E5EFEC4199D8BFA0098A9D2B.pdf	/repo/data/pdfs/fr/2025/225C1139.pdf	2026-05-19 14:23:12.475486+00	2026-05-19 14:23:12.475486+00	\N
48	FR	225C1003	\N	\N	ALTAMIR	AMBOISE SAS	2025-06-16	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1003/05ABE9DBA29A5ECF05C9F78B5AE905C73FB41BD48C6980F685BFE28737829D77.pdf	/repo/data/pdfs/fr/2025/225C1003.pdf	2026-05-19 14:23:12.497229+00	2026-05-19 14:23:12.497229+00	\N
49	FR	225C0995	\N	\N	GROUPE ETPO SA	GROUPE SPIE BATIGNOLLES SAS	2025-06-13	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0995/89F80B88B4C39CB8BE6C6E00CE15DED65CC13580E802F7616A1FF8EB217C8E76.pdf	/repo/data/pdfs/fr/2025/225C0995.pdf	2026-05-19 14:23:12.524803+00	2026-05-19 14:23:12.524803+00	\N
50	FR	225C0943	\N	\N	TARKETT S.A.	[pending parse]	2025-06-06	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0943/2766C94AB6689E31301176B6AB33C47F5BFA24283DFC719261629B63E795CE80.pdf	/repo/data/pdfs/fr/2025/225C0943.pdf	2026-05-19 14:23:12.555246+00	2026-05-19 14:23:12.555246+00	\N
51	FR	225C0929	\N	\N	VERALLIA	[pending parse]	2025-11-28	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0929/F0920AB04DC74434B52DD0FE7CB8BD0D0848FBCA912571968BD0585BAF6E0DA4.pdf	/repo/data/pdfs/fr/2025/225C0929.pdf	2026-05-19 14:23:12.796878+00	2026-05-19 14:23:12.796878+00	\N
52	FR	225C0921	\N	\N	M2I	ABILWAYS	2025-06-06	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0921/598AEEE4C8C8BA22E6E8F10899BF9587CAB180EDE7FD1370A2FC31000A928867.pdf	/repo/data/pdfs/fr/2025/225C0921.pdf	2026-05-19 14:23:12.824991+00	2026-05-19 14:23:12.824991+00	\N
53	FR	225C0920	\N	\N	BELIEVE	[pending parse]	2025-06-05	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0920/EFA14EF47EA8E982099F77768E6D5DB5982A1FB2DD38ADF653B80696FF46ED09.pdf	/repo/data/pdfs/fr/2025/225C0920.pdf	2026-05-19 14:23:12.844884+00	2026-05-19 14:23:12.844884+00	\N
54	FR	225C0845	\N	\N	UNIBEL	[pending parse]	2025-05-26	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0845/5959CDC36EEA75D9BB16F9817DF6C7314CE63D89790E33FEB1DA8C70DFF12CC7.pdf	/repo/data/pdfs/fr/2025/225C0845.pdf	2026-05-19 14:23:12.870305+00	2026-05-19 14:23:12.870305+00	\N
55	FR	225C0838	\N	\N	GROUPE ETPO SA	GROUPE SPIE BATIGNOLLES SAS	2025-05-22	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0838/7C5773E08924691DD74132E2C661DB3DE388B66A8E0BB41F5FADB7D71B0D3202.pdf	/repo/data/pdfs/fr/2025/225C0838.pdf	2026-05-19 14:23:12.895311+00	2026-05-19 14:23:12.895311+00	\N
56	FR	225C0741	\N	\N	FINANCIERE MONCEY	BOLLORE SE	2025-05-05	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0741/17E366B209E9E2ED0180EB9A7C7B00839735621223DF35947F824CB4EFE1E12D.pdf	/repo/data/pdfs/fr/2025/225C0741.pdf	2026-05-19 14:23:12.921746+00	2026-05-19 14:23:12.921746+00	\N
57	FR	225C0740	\N	\N	COMPAGNIE DU CAMBODGE	BOLLORE SE	2025-05-05	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0740/1283751425D68B1A5DF96C9EC10E51976B0C0CEE68842E85A9393EC463C78975.pdf	/repo/data/pdfs/fr/2025/225C0740.pdf	2026-05-19 14:23:12.948083+00	2026-05-19 14:23:12.948083+00	\N
58	FR	225C0739	\N	\N	SOCIETE INDUSTRIELLE ET FINANCIERE DE L'ARTOIS	BOLLORE SE	2025-11-28	opr	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0739/49EDABB0E59E6DFB2185881C48662DD85049EDD259627F0F16D69C6A9FFDF6A4.pdf	/repo/data/pdfs/fr/2025/225C0739.pdf	2026-05-19 14:23:12.973616+00	2026-05-19 14:23:12.973616+00	\N
59	FR	225C0725	\N	\N	M2I	ABILWAYS	2025-06-06	opa_simplifiee	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0725/686E4EA41EA6F49A0DDF69C4D06BBD4A0CE2D1FB6D7F3A165F8BB9E22B2AABE2.pdf	/repo/data/pdfs/fr/2025/225C0725.pdf	2026-05-19 14:23:12.998852+00	2026-05-19 14:23:12.998852+00	\N
60	FR	225C0708	\N	\N	VERALLIA	[pending parse]	2025-06-06	opa	announced	\N	EUR	\N	\N	\N	\N	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0708/307129575A270937D25873228E87EF688B894D56B00E9385B4121A76FCC35177.pdf	/repo/data/pdfs/fr/2025/225C0708.pdf	2026-05-19 14:23:13.026591+00	2026-05-19 14:23:13.026591+00	\N
326	IT	CONSOB-opa_bancasistema_20260511	\N	\N	Banca Sistema Spa	Banca CF+ Credito Fondiario Spa	2026-05-11	opas	announced	1.890000	EUR	\N	\N	\N	2026-06-12	https://www.consob.it/documents/11973/11173223/opa_bancasistema_20260511.pdf/6a2eb96e-07be-acdb-bce8-4c9718262999?version=1.0&t=1777986457850&download=false	/repo/data/pdfs/it/2026/CONSOB-opa_bancasistema_20260511.pdf	2026-05-19 14:41:51.620512+00	2026-05-19 14:41:51.620512+00	\N
327	IT	CONSOB-opa_cir_20260427	\N	\N	[pending parse]	Cir Spa	2026-04-27	opa_volontaire_parziale	announced	0.680000	EUR	\N	\N	\N	2026-05-18	https://www.consob.it/documents/11973/11173223/opa_cir_20260427.pdf/d7e8402c-5a89-5a9a-3e0b-62f4dfc18e7c?version=1.0&t=1778228094244&download=false	/repo/data/pdfs/it/2026/CONSOB-opa_cir_20260427.pdf	2026-05-19 14:41:52.680171+00	2026-05-19 14:41:52.680171+00	\N
328	IT	CONSOB-opa_danzic_20260424	\N	\N	Digital Value Spa	Oep Danzig BidCo Spa	2026-04-24	opa_obligatoire	announced	29.000000	EUR	\N	\N	\N	2026-05-15	https://www.consob.it/documents/11973/11173223/opa_danzic_20260424.pdf/39710032-6eba-f885-0d5d-14f0c471aaa7?version=1.0&t=1776951574254&download=false	/repo/data/pdfs/it/2026/CONSOB-opa_danzic_20260424.pdf	2026-05-19 14:41:54.653175+00	2026-05-19 14:41:54.653175+00	\N
329	IT	CONSOB-opa_nextre_20260420	\N	\N	Next Re SIIQ Spa	CPI Property Group Sa	2026-04-20	opa_volontaire_totalitaria	announced	3.000000	EUR	\N	\N	\N	2026-05-15	https://www.consob.it/documents/11973/11173223/opa_nextre_20260420.pdf/21d78c73-9007-5f13-d370-61662d7e0b86?version=1.0&t=1776437533321&download=false	/repo/data/pdfs/it/2026/CONSOB-opa_nextre_20260420.pdf	2026-05-19 14:41:56.697586+00	2026-05-19 14:41:56.697586+00	\N
330	IT	CONSOB-opa_banco_desio_20260330	\N	\N	Solutions Capital Management Sim Spa	Banco di Desio e della Brianza Spa	2026-03-30	opa_volontaire_totalitaria	announced	4.610000	EUR	\N	\N	\N	2026-04-24	https://www.consob.it/documents/11973/11173223/opa_banco_desio_20260330.pdf/07c7630b-2422-c466-f966-4a812e9410ae?version=1.0&t=1775034768682&download=false	/repo/data/pdfs/it/2026/CONSOB-opa_banco_desio_20260330.pdf	2026-05-19 14:41:58.115651+00	2026-05-19 14:41:58.115651+00	\N
331	IT	CONSOB-opa_ferretti_20260316	\N	\N	Ferretti Spa	Azúr as	2026-03-16	opa_volontaire_parziale	announced	3.500000	EUR	\N	\N	\N	2026-04-13	https://www.consob.it/documents/11973/11173223/opa_ferretti_20260316.pdf/08cdbfd3-2ef7-5a64-c6fa-82636ac7ad41?version=1.0&t=1773053920134&download=false	/repo/data/pdfs/it/2026/CONSOB-opa_ferretti_20260316.pdf	2026-05-19 14:41:58.947139+00	2026-05-19 14:41:58.947139+00	\N
332	IT	CONSOB-opa_Tinexta_20260223	\N	\N	Tinexta Spa	[pending parse]	2026-02-23	opa_obligatoire	announced	15.000000	EUR	\N	\N	\N	2026-03-20	https://www.consob.it/documents/11973/11173223/opa_Tinexta_20260223.pdf/a1f842fa-0198-9f35-8d33-58831af87412?version=1.0&t=1771835796072&download=false	/repo/data/pdfs/it/2026/CONSOB-opa_Tinexta_20260223.pdf	2026-05-19 14:42:00.620218+00	2026-05-19 14:42:00.620218+00	\N
333	IT	CONSOB-opa_antares_20260216	\N	\N	[pending parse]	[pending parse]	2026-02-16	opa_obligatoire	announced	5.000000	EUR	\N	\N	\N	2026-03-06	https://www.consob.it/documents/11973/11173223/opa_antares_20260216.pdf/3d16d01f-e8d0-32eb-6dad-b3aefab28c5f?version=1.0&t=1771247533790&download=false	/repo/data/pdfs/it/2026/CONSOB-opa_antares_20260216.pdf	2026-05-19 14:42:02.763663+00	2026-05-19 14:42:02.763663+00	\N
334	IT	CONSOB-opa_health_italia_20260409	\N	\N	Health Italia Spa	Lonvita Spa	2026-02-09	opa_obligatoire	announced	300.000000	EUR	\N	\N	\N	2026-03-06	https://www.consob.it/documents/11973/11173223/opa_health_italia_20260409.pdf/63a6f544-5c05-5c36-e3f4-620d67ae7972?version=1.0&t=1770374793287&download=false	/repo/data/pdfs/it/2026/CONSOB-opa_health_italia_20260409.pdf	2026-05-19 14:42:05.37448+00	2026-05-19 14:42:05.37448+00	\N
335	IT	CONSOB-opas_Banca_Sistema_20260116	\N	\N	Banca Sistema Spa	Banca CF+ Credito Fondiario Spa	2026-01-16	opas	announced	1.800000	EUR	\N	\N	\N	2026-02-27	https://www.consob.it/documents/11973/11173223/opas_Banca_Sistema_20260116.pdf/35910c2c-1d58-445e-c93c-a297cb5f3557?version=1.0&t=1768571745569&download=false	/repo/data/pdfs/it/2026/CONSOB-opas_Banca_Sistema_20260116.pdf	2026-05-19 14:42:06.385427+00	2026-05-19 14:42:06.385427+00	\N
336	IT	CONSOB-opa_eles_20260105	\N	\N	Eles Semiconductor Equipment Spa	Ebidco srl	2026-01-05	opa_obligatoire	announced	2.650000	EUR	\N	\N	\N	2026-02-06	https://www.consob.it/documents/11973/9797550/opa_eles_20260105.pdf/18a730f7-de22-6923-1c48-b61f81cba606?version=1.0&t=1766135766099&download=false	/repo/data/pdfs/it/2026/CONSOB-opa_eles_20260105.pdf	2026-05-19 14:42:07.43528+00	2026-05-19 14:42:07.43528+00	\N
337	IT	CONSOB-opa_spindox_20251215	\N	\N	Spindox Spa	BackSpin Spa	2025-12-15	opa_obligatoire	announced	13.000000	EUR	\N	\N	\N	2026-01-16	https://www.consob.it/documents/11973/9797550/opa_spindox_20251215.pdf/05e590ab-3b41-70e4-dd5a-3993e348c7f1?version=1.0&t=1765794867359&download=false	/repo/data/pdfs/it/2025/CONSOB-opa_spindox_20251215.pdf	2026-05-19 14:42:08.87038+00	2026-05-19 14:42:08.87038+00	\N
338	IT	CONSOB-opa_mare_20251205	\N	\N	Eles Semiconductor Equipment Spa	Mare Engineering Group Spa	2025-12-05	opa_volontaire_totalitaria	announced	2.610000	EUR	\N	\N	\N	2025-12-30	https://www.consob.it/documents/11973/9797550/opa_mare_20251205.pdf/efe44fae-dbee-db5a-6b36-6dc1d011d52e?version=1.0&t=1764331106900&download=false	/repo/data/pdfs/it/2025/CONSOB-opa_mare_20251205.pdf	2026-05-19 14:42:09.874764+00	2026-05-19 14:42:09.874764+00	\N
339	IT	CONSOB-opa_ala_20251201	\N	\N	Ala Spa	Wing BidCo Spa	2025-12-01	opa_obligatoire	announced	36.080000	EUR	\N	\N	\N	2025-12-19	https://www.consob.it/documents/11973/9797550/opa_ala_20251201.pdf/2a6a3d66-37c0-f56c-ac6b-41cadd8ab468?version=1.0&t=1765359905870&download=false	/repo/data/pdfs/it/2025/CONSOB-opa_ala_20251201.pdf	2026-05-19 14:42:12.707756+00	2026-05-19 14:42:12.707756+00	\N
340	IT	CONSOB-opa_almawave_20251117	\N	\N	Almawave Spa	Almaviva Spa	2025-11-17	opa_volontaire_totalitaria	announced	4.300000	EUR	\N	\N	\N	2025-12-05	https://www.consob.it/documents/11973/9797550/opa_almawave_20251117.pdf/aee6d015-accb-eac7-2e08-481fec834ea2?version=1.0&t=1763130632619&download=false	/repo/data/pdfs/it/2025/CONSOB-opa_almawave_20251117.pdf	2026-05-19 14:42:14.114292+00	2026-05-19 14:42:14.114292+00	\N
341	IT	CONSOB-opa_palingeo_20251027	\N	\N	Palingeo	Icop Spa Società Benefit	2025-10-27	opa_obligatoire	announced	6.000000	EUR	\N	\N	\N	2025-11-14	https://www.consob.it/documents/11973/9797550/opa_palingeo_20251027.pdf/cf025b6c-b585-7cf4-3224-6ed2fc9fc433?version=1.0&t=1761559308256&download=false	/repo/data/pdfs/it/2025/CONSOB-opa_palingeo_20251027.pdf	2026-05-19 14:42:16.037318+00	2026-05-19 14:42:16.037318+00	\N
342	IT	CONSOB-ops_montepaschi_20250714	\N	\N	Mediobanca-Banca di Credito Finanziario Spa	Banca Monte dei Paschi di Siena Spa	2025-07-14	opas	announced	\N	EUR	\N	\N	\N	2025-09-08	https://www.consob.it/documents/11973/9797550/ops_montepaschi_20250714.pdf/3c5564d1-e993-8042-0f67-aa8ca1264b0e?version=1.0&t=1751693617850&download=false	/repo/data/pdfs/it/2025/CONSOB-ops_montepaschi_20250714.pdf	2026-05-19 14:42:17.266828+00	2026-05-19 14:42:17.266828+00	\N
343	IT	CONSOB-opa_bialetti_20250707	\N	\N	Bialetti Spa	Octagon BidCo Spa	2025-07-07	opa_obligatoire	announced	0.467000	EUR	\N	\N	\N	2025-07-25	https://www.consob.it/documents/11973/9797550/opa_bialetti_20250707.pdf/ec0fe530-d442-b144-3bf2-7a86415326a7?version=1.0&t=1752150728895&download=false	/repo/data/pdfs/it/2025/CONSOB-opa_bialetti_20250707.pdf	2026-05-19 14:42:18.786588+00	2026-05-19 14:42:18.786588+00	\N
344	IT	CONSOB-ops_Banca_Popolare_Sondrio_20250616	\N	\N	Banca Popolare di Sondrio S	[pending parse]	2025-06-16	opas	announced	\N	EUR	\N	\N	\N	2025-07-11	https://www.consob.it/documents/11973/9797550/ops_Banca_Popolare_Sondrio_20250616.pdf/f554472c-33fe-1ede-ad0e-63d53f5ff8fa?version=1.0&t=1749203433633&download=false	/repo/data/pdfs/it/2025/CONSOB-ops_Banca_Popolare_Sondrio_20250616.pdf	2026-05-19 14:42:19.782273+00	2026-05-19 14:42:19.782273+00	\N
345	IT	CONSOB-opa_Alkemy_20250609	\N	\N	Alkemy S	[pending parse]	2025-06-09	opa_volontaire_totalitaria	announced	12.000000	EUR	\N	\N	\N	2025-07-04	https://www.consob.it/documents/11973/9797550/opa_Alkemy_20250609.pdf/7d34b102-d152-787c-41ac-e5152d1fadd9?version=1.0&t=1749480240987&download=false	/repo/data/pdfs/it/2025/CONSOB-opa_Alkemy_20250609.pdf	2026-05-19 14:42:20.753545+00	2026-05-19 14:42:20.753545+00	\N
346	IT	CONSOB-Opa_IlSole24Ore_20250603	\N	\N	Il Sole 24 Ore Spa	Zenit Spa	2025-06-03	opa_volontaire_totalitaria	announced	1.100000	EUR	\N	\N	\N	2025-06-30	https://www.consob.it/documents/11973/9797550/Opa_IlSole24Ore_20250603.pdf/9f1eaf2d-4eb3-3612-aab0-b7eb2eb29598?version=1.0&t=1748421998484&download=false	/repo/data/pdfs/it/2025/CONSOB-Opa_IlSole24Ore_20250603.pdf	2026-05-19 14:42:21.747038+00	2026-05-19 14:42:21.747038+00	\N
347	IT	CONSOB-opa_illimity_20250519	\N	\N	Illimity Bank Spa	Banca Ifis Spa	2025-05-19	opas	announced	1.414000	EUR	\N	\N	\N	2025-06-27	https://www.consob.it/documents/11973/9797550/opa_illimity_20250519.pdf/4c9b537c-54b0-0057-357a-451785b2511d?version=1.0&t=1747032853909&download=false	/repo/data/pdfs/it/2025/CONSOB-opa_illimity_20250519.pdf	2026-05-19 14:42:22.993737+00	2026-05-19 14:42:22.993737+00	\N
348	DE	BAFIN-DE000CBK1001-20260505	DE000CBK1001	\N	COMMERZBANK Aktiengesellschaft	UniCredit S.p.A	2026-05-05	opa_volontaire_totalitaria	announced	1.000000	EUR	\N	\N	\N	\N	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/commerzbank.html?nn=151388	/repo/data/pdfs/de/2026/BAFIN-DE000CBK1001-20260505.pdf	2026-05-19 16:22:30.99317+00	2026-05-19 16:22:30.99317+00	\N
349	DE	BAFIN-DE000KC01000-20260205	DE000KC01000	\N	Klöckner & Co SE	Worthington Steel GmbH	2026-02-05	opa_volontaire_totalitaria	announced	11.000000	EUR	\N	\N	\N	\N	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/kloeckner-co-se-2.html?nn=151388	/repo/data/pdfs/de/2026/BAFIN-DE000KC01000-20260205.pdf	2026-05-19 16:22:31.711996+00	2026-05-19 16:22:31.711996+00	\N
350	DE	BAFIN-DE000A0Z1JH9-20251117	DE000A0Z1JH9	\N	PSI Software SE	Zest Bidco GmbH	2025-11-17	opa_volontaire_totalitaria	announced	45.000000	EUR	\N	\N	\N	\N	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/PSI_Software.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE000A0Z1JH9-20251117.pdf	2026-05-19 16:22:32.887981+00	2026-05-19 16:22:32.887981+00	\N
351	DE	BAFIN-DE0007504508-20251021	DE0007504508	\N	Turbon AG	S77 Holdings GmbH	2025-10-21	opa_obligatoire	announced	3.340000	EUR	\N	\N	\N	\N	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/turbon.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE0007504508-20251021.pdf	2026-05-19 16:22:33.698063+00	2026-05-19 16:22:33.698063+00	\N
352	DE	BAFIN-DE000A1E89S5-20251002	DE000A1E89S5	\N	Readcrest Capital AG	Obotritia Capital KGaA	2025-10-02	opa_volontaire_totalitaria	announced	1.300000	EUR	\N	\N	\N	2024-12-31	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/readcrest_capital.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE000A1E89S5-20251002.pdf	2026-05-19 16:22:34.922166+00	2026-05-19 16:22:34.922166+00	\N
353	DE	BAFIN-DE0007257503-20250901	DE0007257503	\N	CECONOMY AG	JINGDONG HOLDING GERMANY GMBH	2025-09-01	opa_volontaire_totalitaria	announced	4.600000	EUR	\N	\N	\N	\N	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/CECONOMY.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE0007257503-20250901.pdf	2026-05-19 16:22:36.013779+00	2026-05-19 16:22:36.013779+00	\N
354	DE	BAFIN-DE000A254294-20250804	DE000A254294	\N	Heidelberger Beteiligungsholding AG	Apeiron Investment Group Ltd	2025-08-04	opa_obligatoire	announced	99.150000	EUR	\N	\N	\N	2024-12-31	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/heidel.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE000A254294-20250804.pdf	2026-05-19 16:22:37.863174+00	2026-05-19 16:22:37.863174+00	\N
355	DE	BAFIN-DE000FPH9000-20250731	DE000FPH9000	\N	Francotyp-Postalia Holding AG	SALTARAX GmbH	2025-07-31	opa_volontaire_parziale	announced	2.800000	EUR	\N	\N	\N	2025-08-28	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Francotyp_Saltarax.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE000FPH9000-20250731.pdf	2026-05-19 16:22:38.90937+00	2026-05-19 16:22:38.90937+00	\N
356	DE	BAFIN-DE0005490601-20250725	DE0005490601	\N	Leo International Precision Health Aktiengesellschaft	SCGI Corporate Finance GmbH	2025-07-25	opa_obligatoire	announced	0.710000	EUR	\N	\N	\N	\N	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Leo_International.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE0005490601-20250725.pdf	2026-05-19 16:22:39.676196+00	2026-05-19 16:22:39.676196+00	\N
357	DE	BAFIN-DE000A2P4LJ5-20250714	DE000A2P4LJ5	\N	PharmaSGP Holding SE	FUTRUE GmbH	2025-07-14	delisting_offer	announced	28.000000	EUR	\N	\N	\N	\N	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/PharmaSGP.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE000A2P4LJ5-20250714.pdf	2026-05-19 16:22:40.630612+00	2026-05-19 16:22:40.630612+00	\N
358	DE	BAFIN-DE000FPH9000-20250709	DE000FPH9000	\N	Francotyp-Postalia Holding AG	Francotyp-Postalia Holding AG	2025-07-09	delisting_offer	announced	2.270000	EUR	\N	\N	\N	2025-08-07	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Francotyp.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE000FPH9000-20250709.pdf	2026-05-19 16:22:41.656531+00	2026-05-19 16:22:41.656531+00	\N
359	DE	BAFIN-DE000A1K0375-20250708	DE000A1K0375	\N	artnet AG	Leonardo Art Holdings GmbH	2025-07-08	delisting_offer	announced	11.250000	EUR	\N	\N	\N	\N	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/artnetAG.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE000A1K0375-20250708.pdf	2026-05-19 16:22:43.022884+00	2026-05-19 16:22:43.022884+00	\N
360	DE	BAFIN-DE000A2E4T77-20250630	DE000A2E4T77	\N	H&R GmbH & Co. KGaA	H&R Holding GmbH	2025-06-30	opa_volontaire_parziale	announced	5.000000	EUR	\N	\N	\N	\N	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/H_R2.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE000A2E4T77-20250630.pdf	2026-05-19 16:22:43.828285+00	2026-05-19 16:22:43.828285+00	\N
361	DE	BAFIN-DE0005545503-20250605	DE0005545503	\N	1&1 AG	United Internet AG	2025-06-05	opa_volontaire_parziale	announced	18.500000	EUR	\N	\N	\N	\N	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/United_Internet.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE0005545503-20250605.pdf	2026-05-19 16:22:45.016545+00	2026-05-19 16:22:45.016545+00	\N
362	DE	BAFIN-DE000PSM7770-20250604	DE000PSM7770	\N	ProSiebenSat.1 Media SE	PPF IM LTD	2025-06-04	opa_volontaire_parziale	announced	7.000000	EUR	\N	\N	\N	\N	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/PPF_IM_LTD.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE000PSM7770-20250604.pdf	2026-05-19 16:22:46.055654+00	2026-05-19 16:22:46.055654+00	\N
363	DE	BAFIN-DE000A288904-20250523	DE000A288904	\N	CompuGroup Medical SE & Co . KGaA	Caesar BidCo GmbH	2025-05-23	delisting_offer	announced	22.000000	EUR	\N	\N	\N	2024-12-05	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Compu.html?nn=151388	/repo/data/pdfs/de/2025/BAFIN-DE000A288904-20250523.pdf	2026-05-19 16:22:47.317421+00	2026-05-19 16:22:47.317421+00	\N
\.


--
-- Data for Name: events; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.events (id, deal_id, ts, event_type, description, source_url, raw_payload, created_at) FROM stdin;
1	1	2026-05-19 14:23:10.79839+00	filing_amf	BDIF note d'information OPAS — visée: POULAILLON (numero 226C0683)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0683/AF100678026C5A3376D19A90BA0FE83D523F43E41FDCF886248CF89772F495D6.pdf	{"numero": "226C0683", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006037", "raison_sociale": "POULAILLON"}], "documents": [{"path": "2026/226C0683/AF100678026C5A3376D19A90BA0FE83D523F43E41FDCF886248CF89772F495D6.pdf", "accessible": true, "nom_fichier": "226C0683.pdf"}, {"path": "2026/226C0683/884F72D2D97F7A152A297C286513D1A3C836C87FE8602806DB5F05AFB52E8305.pdf", "accessible": true, "nom_fichier": "226C068300.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2026-05-18T17:36:05.258197+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:10.781503+00
2	2	2026-05-19 14:23:10.848228+00	filing_amf	BDIF note d'information OPR — visée: MEDIA 6 (numero 226C0661)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0661/954781AD2F1F1BF3816AA9C708025BF72D9C54D8CFCF908238AD85B40E413D3B.pdf	{"numero": "226C0661", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003282", "raison_sociale": "MEDIA 6"}], "documents": [{"path": "2026/226C0661/954781AD2F1F1BF3816AA9C708025BF72D9C54D8CFCF908238AD85B40E413D3B.pdf", "accessible": true, "nom_fichier": "226C0661.pdf"}, {"path": "2026/226C0661/A78F3F74555D43713BA6A4E7335EB02F7F97723CBB53196AFBB57737C335393B.pdf", "accessible": true, "nom_fichier": "226C066100.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-05-11T18:36:03.753711+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:10.845166+00
3	3	2026-05-19 14:23:10.885879+00	filing_amf	BDIF note d'information OPR — visée: MEDIA 6 (numero 226C0645)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0645/FE0616923D43D1F060E72056AFCF74F91E1A385883F3C547318A36E8027D6E2E.pdf	{"numero": "226C0645", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003282", "raison_sociale": "MEDIA 6"}], "documents": [{"path": "2026/226C0645/FE0616923D43D1F060E72056AFCF74F91E1A385883F3C547318A36E8027D6E2E.pdf", "accessible": true, "nom_fichier": "226C0645.pdf"}, {"path": "2026/226C0645/16C2EBE57BC3D54D636D0683B0E3627204B06A2020698C5809C8E5E48F47112F.pdf", "accessible": true, "nom_fichier": "226C064500.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-05-07T18:06:08.722818+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:10.884163+00
4	4	2026-05-19 14:23:10.923116+00	filing_amf	BDIF note d'information OPA — visée: FNAC DARTY (numero 226C0644)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0644/72DF20BE22E022A2C30DC6186B5CC3F77B31B85FA0D84EE9D1465AF96DF8A90C.pdf	{"numero": "226C0644", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005518", "raison_sociale": "FNAC DARTY"}], "documents": [{"path": "2026/226C0644/72DF20BE22E022A2C30DC6186B5CC3F77B31B85FA0D84EE9D1465AF96DF8A90C.pdf", "accessible": true, "nom_fichier": "226C0644.pdf"}, {"path": "2026/226C0644/18D9F8430751A07C88629CC435BD1B602E656443C533118CC0F1100EF8BC2403.pdf", "accessible": true, "nom_fichier": "226C064400.pdf"}, {"path": "2026/226C0644/541FFFF730DDD7000A6E588D16DD6DFD34B640308CF95D089AE442DB34E64D9E.pdf", "accessible": true, "nom_fichier": "226C064401.pdf"}, {"path": "2026/226C0644/9DB13672CA593901B7B8E8E95BCE77B84AEA0867E3C2DD0F0E24630DDE2F16FA.pdf", "accessible": true, "nom_fichier": "226C064402.pdf"}, {"path": "2026/226C0644/A53FB5CA3523408CB157219361FDBD07C147A48BBC5EFB2CAD3B151756BB98E8.pdf", "accessible": true, "nom_fichier": "226C064403.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2026-05-12T11:45:45.890467+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:10.921401+00
5	5	2026-05-19 14:23:10.964189+00	filing_amf	BDIF note d'information OPAS — visée: VINPAI (numero 226C0620)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0620/C88737C27EBA36B4ABE577D1CF942FADDF3FCB9A27BDA639FEA0105D816741C4.pdf	{"numero": "226C0620", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007943", "raison_sociale": "VINPAI"}], "documents": [{"path": "2026/226C0620/C88737C27EBA36B4ABE577D1CF942FADDF3FCB9A27BDA639FEA0105D816741C4.pdf", "accessible": true, "nom_fichier": "226C0620.pdf"}, {"path": "2026/226C0620/A842B4E896DB2C73C7F29CB6541C5930A0912BDBD16D8F4792FE5FD47D7C4510.pdf", "accessible": true, "nom_fichier": "226C062000.pdf"}, {"path": "2026/226C0620/DB5E46156AF748648D1C9ED6FFA1CE1E0820B4A1FA371A86FB3DA1A78EAE9BB6.pdf", "accessible": true, "nom_fichier": "226C062001.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2026-05-04T18:52:04.735592+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:10.961674+00
6	6	2026-05-19 14:23:11.008414+00	filing_amf	BDIF note d'information OPA — visée: ELECTRICITE ET EAUX DE MADAGASCAR (numero 226C0591)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0591/348695808BFBEBA6FD7244F05D2B43B6FB5C3DDBB70A75CFDDE0145335D82145.pdf	{"numero": "226C0591", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001534", "raison_sociale": "ELECTRICITE ET EAUX DE MADAGASCAR"}], "documents": [{"path": "2026/226C0591/348695808BFBEBA6FD7244F05D2B43B6FB5C3DDBB70A75CFDDE0145335D82145.pdf", "accessible": true, "nom_fichier": "226C0591.pdf"}, {"path": "2026/226C0591/FEB1B19F879934C47E2B995032733FBF0394C9D31EE247E1C32F6B29AF84B7D7.pdf", "accessible": true, "nom_fichier": "226C059100.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2026-04-28T08:06:04.912486+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.006923+00
7	7	2026-05-19 14:23:11.04486+00	filing_amf	BDIF note d'information OPAS — visée: POULAILLON (numero 226C0578)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0578/B956DC68725674FD12F3349D2160F0F214B32A3B47E1E2C948F36C10F05C7C1D.pdf	{"numero": "226C0578", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006037", "raison_sociale": "POULAILLON"}], "documents": [{"path": "2026/226C0578/B956DC68725674FD12F3349D2160F0F214B32A3B47E1E2C948F36C10F05C7C1D.pdf", "accessible": true, "nom_fichier": "226C0578.pdf"}, {"path": "2026/226C0578/E1AD7B3A6520A18790790C6234997ADD2C56B999F999A75DB4DE7A75B7F97D21.pdf", "accessible": true, "nom_fichier": "226C057800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2026-04-23T18:00:04.534170+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.043373+00
8	8	2026-05-19 14:23:11.08148+00	filing_amf	BDIF note d'information OPR — visée: TERACT (numero 226C0550)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0550/790CEA3A90861D7F49FCC7EC86FDEE425D31E42EEA5597D127F45DCF68783FB8.pdf	{"numero": "226C0550", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007211", "raison_sociale": "TERACT"}], "documents": [{"path": "2026/226C0550/790CEA3A90861D7F49FCC7EC86FDEE425D31E42EEA5597D127F45DCF68783FB8.pdf", "accessible": true, "nom_fichier": "226C0550.pdf"}, {"path": "2026/226C0550/62A8D6328F183E53AF0F1067FD6F67A0624E5BB41B18D9408F04FF576738B7BB.pdf", "accessible": true, "nom_fichier": "226C055000.pdf"}, {"path": "2026/226C0550/6A7B9D3A5756581539366032643CE0298AE74A588BB1D52FFD7AF2575A4446F5.pdf", "accessible": true, "nom_fichier": "226C055001.pdf"}, {"path": "2026/226C0550/01D20837BA9794A8678E8D6289B556AD4596AF630A4F9A255BA407512E1A7C1A.pdf", "accessible": true, "nom_fichier": "226C055002.pdf"}, {"path": "2026/226C0550/9FDB2188C43A9108A8275646608079AEC0818A898823F7E0C6AEC7406132C10D.pdf", "accessible": true, "nom_fichier": "226C055003.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-04-20T17:54:05.301708+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.079566+00
9	9	2026-05-19 14:23:11.111851+00	filing_amf	BDIF note d'information OPR — visée: SOCIETE DE LA TOUR EIFFEL (numero 226C0538)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0538/F1A0A887F62CDDB65C1D688EA3F99A87CCBF26975A738C848CFAF5EB83C3E9AB.pdf	{"numero": "226C0538", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001493", "raison_sociale": "SOCIETE DE LA TOUR EIFFEL"}], "documents": [{"path": "2026/226C0538/F1A0A887F62CDDB65C1D688EA3F99A87CCBF26975A738C848CFAF5EB83C3E9AB.pdf", "accessible": true, "nom_fichier": "226C0538.pdf"}, {"path": "2026/226C0538/25B741123069FBC4D61F9B59471449E098DDCDFB6D48897AE9DCD5B1D79BAD7D.pdf", "accessible": true, "nom_fichier": "226C053800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-04-17T17:38:03.947179+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.110069+00
10	10	2026-05-19 14:23:11.16382+00	filing_amf	BDIF note d'information OPR — visée: MEDIA 6 (numero 226C0531)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0531/561AA4EE77DE083659474F2355A75F1A1AFA156AD34FED1FC6872CCF0A07CE87.pdf	{"numero": "226C0531", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003282", "raison_sociale": "MEDIA 6"}], "documents": [{"path": "2026/226C0531/561AA4EE77DE083659474F2355A75F1A1AFA156AD34FED1FC6872CCF0A07CE87.pdf", "accessible": true, "nom_fichier": "226C0531.pdf"}, {"path": "2026/226C0531/46CD7E6A422170B10E4FF91220D5709F1AA4F58DDBCD130C2B95EADC69D288E3.pdf", "accessible": true, "nom_fichier": "226C053100.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-04-16T18:20:06.256193+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.162304+00
11	11	2026-05-19 14:23:11.200562+00	filing_amf	BDIF note d'information OPR — visée: GAUMONT (numero 226C0511)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0511/AB617FF3C053B29C0869579FC6C94E567E94EF5CA54AD731BEFC90096BF14FB9.pdf	{"numero": "226C0511", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003344", "raison_sociale": "GAUMONT"}], "documents": [{"path": "2026/226C0511/AB617FF3C053B29C0869579FC6C94E567E94EF5CA54AD731BEFC90096BF14FB9.pdf", "accessible": true, "nom_fichier": "226C0511.pdf"}, {"path": "2026/226C0511/1F861B203CC9A83794E4B23052AFA9661EC88CB447C7B30637A44FE4660FB0AA.pdf", "accessible": true, "nom_fichier": "226C051100.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-04-13T18:48:03.869355+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.198702+00
12	12	2026-05-19 14:23:11.234794+00	filing_amf	BDIF note d'information OPR — visée: BALYO (numero 226C0347)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0347/0B2F7A8AF7A42A5DB26EAA3C63A63EAEB4397FC23899488D3EE974E2276033AD.pdf	{"numero": "226C0347", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006437", "raison_sociale": "BALYO"}], "documents": [{"path": "2026/226C0347/0B2F7A8AF7A42A5DB26EAA3C63A63EAEB4397FC23899488D3EE974E2276033AD.pdf", "accessible": true, "nom_fichier": "226C0347.pdf"}, {"path": "2026/226C0347/3134C747EE8DAE1498BC80E42178A379592F1A003FA4D59E32EE8399C88DC870.pdf", "accessible": true, "nom_fichier": "226C034700.pdf"}, {"path": "2026/226C0347/4BA9FF38A00BCF72BFE3D3648B78D40C1C0E71DE87E7388E334429856FE4EF85.pdf", "accessible": true, "nom_fichier": "226C034701.pdf"}, {"path": "2026/226C0347/1C313FC88D91EE393AD161781DEBA691B25B3A349F6D408AE1CB1CEB9352758D.pdf", "accessible": true, "nom_fichier": "226C034702.pdf"}, {"path": "2026/226C0347/6B82B960E85542445EC283217BB50452CD7D1FC65FDDCCEA333248BD28AEBC4F.pdf", "accessible": true, "nom_fichier": "226C034703.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-03-19T18:12:10.895278+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.232917+00
13	13	2026-05-19 14:23:11.267079+00	filing_amf	BDIF note d'information OPR — visée: MEDIA 6 (numero 226C0318)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0318/2E2150D58F6F479C2C8EF560F6397E1558E9AF7DDB22A89699FC6027C7914D34.pdf	{"numero": "226C0318", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003282", "raison_sociale": "MEDIA 6"}], "documents": [{"path": "2026/226C0318/2E2150D58F6F479C2C8EF560F6397E1558E9AF7DDB22A89699FC6027C7914D34.pdf", "accessible": true, "nom_fichier": "226C0318.pdf"}, {"path": "2026/226C0318/EF0A7650F909E5770149C02A5FF714B769F0E8F7DAF67ACE6FD786BB8B0EFDD9.pdf", "accessible": true, "nom_fichier": "226C031800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-03-16T17:42:04.065254+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.264895+00
21	21	2026-05-19 14:23:11.752254+00	filing_amf	BDIF note d'information OPRA — visée: GROUPE TERA (numero 226C0008)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0008/CFFC2BF9EC93BB0D5C735AC1596CCD7BAE08ACB2F02F38BE5E387266621C223E.pdf	{"numero": "226C0008", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006841", "raison_sociale": "GROUPE TERA"}], "documents": [{"path": "2026/226C0008/CFFC2BF9EC93BB0D5C735AC1596CCD7BAE08ACB2F02F38BE5E387266621C223E.pdf", "accessible": true, "nom_fichier": "226C0008.pdf"}, {"path": "2026/226C0008/77073798CB5A2CA59C4F1CC62576052BE56474525F19A2529344564932DFDDDD.pdf", "accessible": true, "nom_fichier": "226C000800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPRA"], "date_information": null, "date_publication": "2026-01-05T18:42:04.170078+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.750639+00
14	14	2026-05-19 14:23:11.299257+00	filing_amf	BDIF note d'information OPA — visée: FNAC DARTY (numero 226C0287)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0287/DBE2E400A000FC29A55CD25156BC15A62A7E389B563ED4E91BC02C772EA0F33F.pdf	{"numero": "226C0287", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005518", "raison_sociale": "FNAC DARTY"}], "documents": [{"path": "2026/226C0287/DBE2E400A000FC29A55CD25156BC15A62A7E389B563ED4E91BC02C772EA0F33F.pdf", "accessible": true, "nom_fichier": "226C0287.pdf"}, {"path": "2026/226C0287/824D3062B190C817B7A4E5D07863722F17686091FDC4D342E7E27F733B9AA6B6.pdf", "accessible": true, "nom_fichier": "226C028700.pdf"}, {"path": "2026/226C0287/41982AC74DB402CBCE4E559CE1EB4160081D7A826E4612E383B9D6271AE0A583.pdf", "accessible": true, "nom_fichier": "226C028701.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2026-03-12T16:38:09.450405+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.297026+00
15	15	2026-05-19 14:23:11.336765+00	filing_amf	BDIF note d'information OPR — visée: TERACT (numero 226C0278)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0278/A31DB49A0FE6CB4A382C7B960FF679D3F9018C80059A4C02ECC31EB5E653A6CE.pdf	{"numero": "226C0278", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007211", "raison_sociale": "TERACT"}], "documents": [{"path": "2026/226C0278/A31DB49A0FE6CB4A382C7B960FF679D3F9018C80059A4C02ECC31EB5E653A6CE.pdf", "accessible": true, "nom_fichier": "226C0278.pdf"}, {"path": "2026/226C0278/43D096BA1C3B2A0FCA0150F896D27D17768F4ED4DCC9809DE880426A377D0EB5.pdf", "accessible": true, "nom_fichier": "226C027800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-03-09T17:58:04.957889+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.334742+00
16	16	2026-05-19 14:23:11.550003+00	filing_amf	BDIF note d'information OPRA — visée: GROUPE TERA (numero 226C0210)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0210/1C1F1BF8B08724AE8CC9283B6501A90015C258F03837A071E732589AE12E82E0.pdf	{"numero": "226C0210", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006841", "raison_sociale": "GROUPE TERA"}], "documents": [{"path": "2026/226C0210/1C1F1BF8B08724AE8CC9283B6501A90015C258F03837A071E732589AE12E82E0.pdf", "accessible": true, "nom_fichier": "226C0210.pdf"}, {"path": "2026/226C0210/D87475DAF86F200458826406D143B817006C0A05A84BFC6D00284C3A1E213E05.pdf", "accessible": true, "nom_fichier": "226C021000.pdf"}, {"path": "2026/226C0210/DF30F144E8A6ACEF2B03E7389F67801FE337F3443A44CF24A15F94D07463D27C.pdf", "accessible": true, "nom_fichier": "226C021001.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions", "ObligationDepotOP"], "types_operation": ["OPRA"], "date_information": null, "date_publication": "2026-02-19T17:44:05.769332+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.548622+00
17	17	2026-05-19 14:23:11.626205+00	filing_amf	BDIF note d'information OPR — visée: TERACT (numero 226C0157)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0157/2954E3860C1959ADF0F7724A2D2E9CF1D89B305D888D3417CE3DF95E46E1D798.pdf	{"numero": "226C0157", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007211", "raison_sociale": "TERACT"}], "documents": [{"path": "2026/226C0157/2954E3860C1959ADF0F7724A2D2E9CF1D89B305D888D3417CE3DF95E46E1D798.pdf", "accessible": true, "nom_fichier": "226C0157.pdf"}, {"path": "2026/226C0157/B9B744E6391FDBE26A645BB267357A04841128BEB0C61F8A30BD48A5DC015F0C.pdf", "accessible": true, "nom_fichier": "226C015700.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-02-05T18:36:25.043043+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.624764+00
18	18	2026-05-19 14:23:11.666884+00	filing_amf	BDIF note d'information OPRA — visée: UV GERMI (numero 226C0156)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0156/66D132B49FB29CB455C97C16A2949728C4D3153D4E3A35EF0F7E7B5E8B9D09CD.pdf	{"numero": "226C0156", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006455", "raison_sociale": "UV GERMI"}], "documents": [{"path": "2026/226C0156/66D132B49FB29CB455C97C16A2949728C4D3153D4E3A35EF0F7E7B5E8B9D09CD.pdf", "accessible": true, "nom_fichier": "226C0156.pdf"}, {"path": "2026/226C0156/C4F529053034B8FB641910F3AE3F8363BC42FCC286D08B5708670C1D7EACA2EB.pdf", "accessible": true, "nom_fichier": "226C015600.pdf"}, {"path": "2026/226C0156/9AA900CB2BE829402B0EE390DCC152F4DEF55C51F132757B757CC913E4EC0853.pdf", "accessible": true, "nom_fichier": "226C015601.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPRA"], "date_information": null, "date_publication": "2026-02-05T18:12:05.949220+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.664168+00
19	19	2026-05-19 14:23:11.692357+00	filing_amf	BDIF note d'information OPAS — visée: SOCIETE DE TAYNINH (numero 226C0095)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0095/69C403AC9DB64955C7CF92305B5B134E2AD8BE64C70A33B64DE758B67E616C68.pdf	{"numero": "226C0095", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00002983", "raison_sociale": "SOCIETE DE TAYNINH"}], "documents": [{"path": "2026/226C0095/69C403AC9DB64955C7CF92305B5B134E2AD8BE64C70A33B64DE758B67E616C68.pdf", "accessible": true, "nom_fichier": "226C0095.pdf"}, {"path": "2026/226C0095/4FB2DC27D0FDCF38064631F24C61EDC2CF01CA2060540A6AC557D40B8CD77574.pdf", "accessible": true, "nom_fichier": "226C009500.pdf"}, {"path": "2026/226C0095/0D7D61E06C293A8796083FB566FFA2C5A489640D9C4F034FFDD477DDD50BBA84.pdf", "accessible": true, "nom_fichier": "226C009501.pdf"}, {"path": "2026/226C0095/69F72D0CDB02A80F1D066A41DDD65916E9D818932FAFF7D2921EB310EE95FDE9.pdf", "accessible": true, "nom_fichier": "226C009502.pdf"}, {"path": "2026/226C0095/4D5E7F38C9C44968C1C2C0C85E181143172504E9DDD054C034FA66DEA0EEB6F7.pdf", "accessible": true, "nom_fichier": "226C009503.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2026-01-23T18:04:08.193553+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.690654+00
20	20	2026-05-19 14:23:11.721025+00	filing_amf	BDIF note d'information OPR — visée: BALYO (numero 226C0020)	https://bdif.amf-france.org/back/api/v1/documents/2026/226C0020/DFF429DF18AF43BC18E7971ABF71A2F5B90B0255B4EBB18EB268F6D1579C2074.pdf	{"numero": "226C0020", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006437", "raison_sociale": "BALYO"}], "documents": [{"path": "2026/226C0020/DFF429DF18AF43BC18E7971ABF71A2F5B90B0255B4EBB18EB268F6D1579C2074.pdf", "accessible": true, "nom_fichier": "226C0020.pdf"}, {"path": "2026/226C0020/FC9756843C80D897883419B09813EC70BDB33A564C55CB13555313D329298372.pdf", "accessible": true, "nom_fichier": "226C002000.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-01-07T10:48:47.000571+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.719628+00
22	22	2026-05-19 14:23:11.789871+00	filing_amf	BDIF note d'information OPR — visée: PRODWARE (numero 225C2156)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2156/ADFDAA0E32B9156501354BF7041F099EE4B743B76ED64C90DE8EB363A1ABCD88.pdf	{"numero": "225C2156", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00004376", "raison_sociale": "PRODWARE"}, {"role": "Initiateur", "jeton": "RS00007540", "raison_sociale": "PHAST INVEST"}], "documents": [{"path": "2025/225C2156/ADFDAA0E32B9156501354BF7041F099EE4B743B76ED64C90DE8EB363A1ABCD88.pdf", "accessible": true, "nom_fichier": "225C2156.pdf"}, {"path": "2025/225C2156/FF4583CCBCC12F33A41E3E94E25DB7DA8E86A119F325214FACCE8D2FDB4B671D.pdf", "accessible": true, "nom_fichier": "225C215600.pdf"}, {"path": "2025/225C2156/506DEF6416E2AFC69FFD8797DBDB41CF7571F5BA4FBBC2CE37E963C448FD4250.pdf", "accessible": true, "nom_fichier": "225C215601.pdf"}, {"path": "2025/225C2156/D6EC858E11C34AF6AC6ED5AC2FA5D25A54102AFC8DD37077070B25325C7ED373.pdf", "accessible": true, "nom_fichier": "225C215602.pdf"}, {"path": "2025/225C2156/CE2ECF9DC3DAD4BD107FFD14F2DDB9B2EA86C63945B371AEBD92A37C844FFDA1.pdf", "accessible": true, "nom_fichier": "225C215603.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-01-23T16:28:07.031231+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.788603+00
23	23	2026-05-19 14:23:11.827216+00	filing_amf	BDIF note d'information OPRA — visée: UV GERMI (numero 225C2136)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2136/B94BBB38882DB1DDE9148BF8D7FD9AF90D3A1681299822A01FC9104155FA4E48.pdf	{"numero": "225C2136", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006455", "raison_sociale": "UV GERMI"}], "documents": [{"path": "2025/225C2136/B94BBB38882DB1DDE9148BF8D7FD9AF90D3A1681299822A01FC9104155FA4E48.pdf", "accessible": true, "nom_fichier": "225C2136.pdf"}, {"path": "2025/225C2136/5A0B405CD03DDF70B5AE3E6A5A842411F069BE4DC542150C891274FBECC6B40F.pdf", "accessible": true, "nom_fichier": "225C213600.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPRA"], "date_information": null, "date_publication": "2025-12-16T18:58:07.314664+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.825417+00
24	24	2026-05-19 14:23:11.858277+00	filing_amf	BDIF note d'information OPA — visée: ELECTRICITE ET EAUX DE MADAGASCAR (numero 225C2135)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2135/5C51631DA1F169C7D81C593980694A6CCD25AE6C6A562F86302C14EDCD2F0C92.pdf	{"numero": "225C2135", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001534", "raison_sociale": "ELECTRICITE ET EAUX DE MADAGASCAR"}], "documents": [{"path": "2025/225C2135/5C51631DA1F169C7D81C593980694A6CCD25AE6C6A562F86302C14EDCD2F0C92.pdf", "accessible": true, "nom_fichier": "225C2135.pdf"}, {"path": "2025/225C2135/E586C60EBE7E7792572B5B5BB29769CB1B3CA5001B9AEE8E046FFC1CF9E9DB07.pdf", "accessible": true, "nom_fichier": "225C213500.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2025-12-17T11:06:05.657990+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.856788+00
25	25	2026-05-19 14:23:11.888268+00	filing_amf	BDIF note d'information OPAS — visée: SOCIETE DE TAYNINH (numero 225C2081)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2081/8CC4832C7F06C4C44A2C8A3798DA63476B655465D14B3460FE2B3DE3C7020FD0.pdf	{"numero": "225C2081", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00002983", "raison_sociale": "SOCIETE DE TAYNINH"}], "documents": [{"path": "2025/225C2081/8CC4832C7F06C4C44A2C8A3798DA63476B655465D14B3460FE2B3DE3C7020FD0.pdf", "accessible": true, "nom_fichier": "225C2081.pdf"}, {"path": "2025/225C2081/1CB74CB3B9731996E10C607A7425CFAAC85E59ECCB0383F7C8074BF461C72941.pdf", "accessible": true, "nom_fichier": "225C208100.pdf"}, {"path": "2025/225C2081/967CDF7AFC396FDB154CCDCE36CB06C040DBD75D4CF11063494C1C677012E0A9.pdf", "accessible": true, "nom_fichier": "225C208101.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-12-08T17:42:05.531411+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.886867+00
26	26	2026-05-19 14:23:11.913758+00	filing_amf	BDIF note d'information OPR — visée: BALYO (numero 225C2063)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2063/4B74E67D96D0415272C70A7A4D4DC3BBE94E2C570A5E4BFFDAB4B0F44776363F.pdf	{"numero": "225C2063", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006437", "raison_sociale": "BALYO"}], "documents": [{"path": "2025/225C2063/4B74E67D96D0415272C70A7A4D4DC3BBE94E2C570A5E4BFFDAB4B0F44776363F.pdf", "accessible": true, "nom_fichier": "225C2063.pdf"}, {"path": "2025/225C2063/94B3F05654D718554CFF1253A7167E0315B809523E2A3B9A484E0D17E0262D3B.pdf", "accessible": true, "nom_fichier": "225C206300.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2026-01-22T16:22:04.902779+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.911954+00
27	27	2026-05-19 14:23:11.94119+00	filing_amf	BDIF note d'information OPAS — visée: COGELEC (numero 225C2061)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C2061/1BE71CDDD093C59BF3C0816994D45C9364CA1D5E1088325B1A6E64CC57C7F564.pdf	{"numero": "225C2061", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006594", "raison_sociale": "COGELEC"}], "documents": [{"path": "2025/225C2061/1BE71CDDD093C59BF3C0816994D45C9364CA1D5E1088325B1A6E64CC57C7F564.pdf", "accessible": true, "nom_fichier": "225C2061.pdf"}, {"path": "2025/225C2061/FF3628690D829BAED7483D2B591ECD0D7F4A6E8E9F4A5F18403623C858587482.pdf", "accessible": true, "nom_fichier": "225C206100.pdf"}, {"path": "2025/225C2061/A0D39344E7D6966FFAA0650F8E8B05B70BE6B98F26A28B8DFDB5C5778A66D96A.pdf", "accessible": true, "nom_fichier": "225C206101.pdf"}, {"path": "2025/225C2061/9827797F2577B1D58D1EA624F05F701FB91DAB226A1E58D12AACAAE6B71D658C.pdf", "accessible": true, "nom_fichier": "225C206102.pdf"}, {"path": "2025/225C2061/2FB9018E61D2C3EF250BAC49A78C7E4F6E4726E657436A0BAD8E9156531F2199.pdf", "accessible": true, "nom_fichier": "225C206103.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2026-01-22T16:36:06.260987+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.939552+00
28	28	2026-05-19 14:23:11.96848+00	filing_amf	BDIF note d'information OPAS — visée: WAGA ENERGY (numero 225C1971)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1971/1561FA645F4D0517BB7B8C3D54435902C7D730202735D1145A8BF8C250D66A3C.pdf	{"numero": "225C1971", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007433", "raison_sociale": "WAGA ENERGY"}], "documents": [{"path": "2025/225C1971/1561FA645F4D0517BB7B8C3D54435902C7D730202735D1145A8BF8C250D66A3C.pdf", "accessible": true, "nom_fichier": "225C1971.pdf"}, {"path": "2025/225C1971/5EE932D9660BB27974F9BDFE36A092E0373355267A490AE6715D9C32933E7F49.pdf", "accessible": true, "nom_fichier": "225C197100.pdf"}, {"path": "2025/225C1971/A8E0778FA3CC87F8A5E219AC2E7BCB6539468667FCDEC8A76810093A8A18BB06.pdf", "accessible": true, "nom_fichier": "225C197101.pdf"}, {"path": "2025/225C1971/7F3D3AC03DC549DABE0F71E1D2DD885C203D62BE00A415A1029367CA17955662.pdf", "accessible": true, "nom_fichier": "225C197102.pdf"}, {"path": "2025/225C1971/4CC4C2226AD906BA1B4114E7C9447005DC173F10FCC1E8EE662F5507EA90EB8A.pdf", "accessible": true, "nom_fichier": "225C197103.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-11-24T09:56:06.101358+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.966245+00
29	29	2026-05-19 14:23:11.99327+00	filing_amf	BDIF note d'information OPR — visée: PRODWARE (numero 225C1924)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1924/278CEE170D11B4B719A5AF39E6EF5D5D98777BCB414E8E0447C8A4C43B17A99C.pdf	{"numero": "225C1924", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00004376", "raison_sociale": "PRODWARE"}, {"role": "Initiateur", "jeton": "RS00007540", "raison_sociale": "PHAST INVEST"}], "documents": [{"path": "2025/225C1924/278CEE170D11B4B719A5AF39E6EF5D5D98777BCB414E8E0447C8A4C43B17A99C.pdf", "accessible": true, "nom_fichier": "225C1924.pdf"}, {"path": "2025/225C1924/740A0D1F6EE2E48B6226EE3D7B33180D14BD955ABFCD6FC62C75755E8D51C787.pdf", "accessible": true, "nom_fichier": "225C192400.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-11-14T16:08:05.330784+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:11.991873+00
30	30	2026-05-19 14:23:12.021881+00	filing_amf	BDIF note d'information OPR — visée: TRONIC'S MICROSYSTEMS S.A. (numero 225C1884)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1884/B2E25865C4580D8F7E0BAA669B6652F2AF700806DAAE34F81EBEE76DC60766A8.pdf	{"numero": "225C1884", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005911", "raison_sociale": "TRONIC'S MICROSYSTEMS S.A."}, {"role": "Initiateur", "jeton": "RS00007557", "raison_sociale": "TDK ELECTRONICS AG"}], "documents": [{"path": "2025/225C1884/B2E25865C4580D8F7E0BAA669B6652F2AF700806DAAE34F81EBEE76DC60766A8.pdf", "accessible": true, "nom_fichier": "225C1884.pdf"}, {"path": "2025/225C1884/1B8FE724D376A7F8E214F4D22166340DC9DA6592839C6E1AF75D5C3C80B9AC48.pdf", "accessible": true, "nom_fichier": "225C188400.pdf"}, {"path": "2025/225C1884/BD2D1A20676E8301501A16EC860E3AE85525635146ADBE9BA3BE381ABABE54D3.pdf", "accessible": true, "nom_fichier": "225C188401.pdf"}, {"path": "2025/225C1884/581AB41E8387DFCBA952EB3E8A4C1550981957E125D75798526A644057066DA9.pdf", "accessible": true, "nom_fichier": "225C188402.pdf"}, {"path": "2025/225C1884/79C4D536B85F91000305A96D8F35524001CED5C3B06FB6B644AFCD10BC8554A2.pdf", "accessible": true, "nom_fichier": "225C188403.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-11-13T10:19:22.946111+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.020703+00
31	31	2026-05-19 14:23:12.04666+00	filing_amf	BDIF note d'information OPR — visée: PRODWARE (numero 225C1797)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1797/18E0F87ABC999B41EECECC8FE71915ACAC89A921DE6C878FBDFA509EEE420DDE.pdf	{"numero": "225C1797", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00004376", "raison_sociale": "PRODWARE"}, {"role": "Initiateur", "jeton": "RS00007540", "raison_sociale": "PHAST INVEST"}], "documents": [{"path": "2025/225C1797/18E0F87ABC999B41EECECC8FE71915ACAC89A921DE6C878FBDFA509EEE420DDE.pdf", "accessible": true, "nom_fichier": "225C1797.pdf"}, {"path": "2025/225C1797/83991376C1D4E98D96D953AD711C3A814BC0CAC07FBB0A8A4C2718DE7AB14880.pdf", "accessible": true, "nom_fichier": "225C179700.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-10-24T14:50:04.584972+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.044928+00
32	32	2026-05-19 14:23:12.073677+00	filing_amf	BDIF note d'information OPA — visée: VOGO (numero 225C1794)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1794/46A8BC8D13F4BFEE1C3F6C7EA75130F3F12717FB75CF6FF6F406DE51A430F10E.pdf	{"numero": "225C1794", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006663", "raison_sociale": "VOGO"}, {"role": "Initiateur", "jeton": "RS00006263", "raison_sociale": "ABEO"}], "documents": [{"path": "2025/225C1794/46A8BC8D13F4BFEE1C3F6C7EA75130F3F12717FB75CF6FF6F406DE51A430F10E.pdf", "accessible": true, "nom_fichier": "225C1794.pdf"}, {"path": "2025/225C1794/A9776B3B941EB44B9C2F6F054D9DF6228B712C3A0D9295387AE71A66357407C7.pdf", "accessible": true, "nom_fichier": "225C179400.pdf"}, {"path": "2025/225C1794/5AAF67FC88026DE37210533BB31C7C64CC3E6F8673C1A745C38D5ED9DC322917.pdf", "accessible": true, "nom_fichier": "225C179401.pdf"}, {"path": "2025/225C1794/782AFA50EA08DD180BABA5B9192149D211428136A1494B83114C754C0CE54CD9.pdf", "accessible": true, "nom_fichier": "225C179402.pdf"}, {"path": "2025/225C1794/5CB7A69744ABFEBED229F405B9963F7F2D74298FA4B1B0EA34306A843E6FB4D5.pdf", "accessible": true, "nom_fichier": "225C179403.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPA", "OPE"], "date_information": null, "date_publication": "2025-11-28T10:58:06.056408+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.072308+00
33	33	2026-05-19 14:23:12.099929+00	filing_amf	BDIF note d'information OPAS — visée: COGELEC (numero 225C1755)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1755/AA36F6148357F70B3CEA5A545CC6F7C5082938EC4B57FCFF4588A719CA34AB0D.pdf	{"numero": "225C1755", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006594", "raison_sociale": "COGELEC"}], "documents": [{"path": "2025/225C1755/AA36F6148357F70B3CEA5A545CC6F7C5082938EC4B57FCFF4588A719CA34AB0D.pdf", "accessible": true, "nom_fichier": "225C1755.pdf"}, {"path": "2025/225C1755/D8E8118785D5D2F62FE03203BD2B410E7B50F25FCA7320B7BA2B24B35D0D7190.pdf", "accessible": true, "nom_fichier": "225C175500.pdf"}, {"path": "2025/225C1755/4781806250AE9E0DB39158048E12177DD27DE66FB22A37E4D62CF112A52D4559.pdf", "accessible": true, "nom_fichier": "225C175501.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-10-15T17:12:06.382581+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.098073+00
34	34	2026-05-19 14:23:12.128989+00	filing_amf	BDIF note d'information OPAS — visée: AGROGENERATION (numero 225C1734)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1734/B3BE65DA8A38EFEF0C6E0B463784BE812AFE929914A3F3416AE80A2CF9A7818E.pdf	{"numero": "225C1734", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005064", "raison_sociale": "AGROGENERATION"}], "documents": [{"path": "2025/225C1734/B3BE65DA8A38EFEF0C6E0B463784BE812AFE929914A3F3416AE80A2CF9A7818E.pdf", "accessible": true, "nom_fichier": "225C1734.pdf"}, {"path": "2025/225C1734/8537D82FACF7C7F1A9C372ACFA8298A2A889E4A485C4D7C80A88A81AC2D4457A.pdf", "accessible": true, "nom_fichier": "225C173400.pdf"}, {"path": "2025/225C1734/D00A905237F64C10F908E3B32D4CF97377EFF231D0B35C506A3359C59B77B701.pdf", "accessible": true, "nom_fichier": "225C173401.pdf"}, {"path": "2025/225C1734/153035C84E493267EFEE5CE74DDA7D13D73F927A3966F51607FC459972151465.pdf", "accessible": true, "nom_fichier": "225C173402.pdf"}, {"path": "2025/225C1734/856EF871EE860CCFFB1BEBE90AE6470B1DA814B8EAB3E7F3B0D2EB5D4B9C9BEC.pdf", "accessible": true, "nom_fichier": "225C173403.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-10-13T08:16:06.421025+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.127561+00
35	35	2026-05-19 14:23:12.15657+00	filing_amf	BDIF note d'information OPAS — visée: WAGA ENERGY (numero 225C1666)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1666/A2460CAD381A8AA7A5E0566E2B02915BD2C21EB7F7F41119354BA67BBCF0C01E.pdf	{"numero": "225C1666", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007433", "raison_sociale": "WAGA ENERGY"}], "documents": [{"path": "2025/225C1666/A2460CAD381A8AA7A5E0566E2B02915BD2C21EB7F7F41119354BA67BBCF0C01E.pdf", "accessible": true, "nom_fichier": "225C1666.pdf"}, {"path": "2025/225C1666/C3424E872C1C3A98D38DA5D776077355D6848AA6513483E0C5EB0F67021D4BD6.pdf", "accessible": true, "nom_fichier": "225C166600.pdf"}, {"path": "2025/225C1666/B5555690F68297698897C6A404EDAAA62698E253E49AAE85C151D892955CF16B.pdf", "accessible": true, "nom_fichier": "225C166601.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-10-02T09:18:05.249381+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.155166+00
36	36	2026-05-19 14:23:12.185493+00	filing_amf	BDIF note d'information OPR — visée: TRONIC'S MICROSYSTEMS S.A. (numero 225C1665)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1665/4BCBC4A976AD1A11A4CFC01F982000092C433608C9B947BF53BA5D350947542F.pdf	{"numero": "225C1665", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005911", "raison_sociale": "TRONIC'S MICROSYSTEMS S.A."}, {"role": "Initiateur", "jeton": "RS00007557", "raison_sociale": "TDK ELECTRONICS AG"}], "documents": [{"path": "2025/225C1665/4BCBC4A976AD1A11A4CFC01F982000092C433608C9B947BF53BA5D350947542F.pdf", "accessible": true, "nom_fichier": "225C1665.pdf"}, {"path": "2025/225C1665/5E5074D4E8D6F3BB6346C689893055F94EFED6EF471B3F4C880B9955683269D6.pdf", "accessible": true, "nom_fichier": "225C166500.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-10-01T14:20:05.056348+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.183876+00
37	37	2026-05-19 14:23:12.211882+00	filing_amf	BDIF note d'information OPAS — visée: AMPLITUDE SURGICAL (numero 225C1629)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1629/8DF9E6C891A17EFCBB495FC63F9C7982DA9D8429C2BCBDA248C9DD77B85D97C3.pdf	{"numero": "225C1629", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006019", "raison_sociale": "AMPLITUDE SURGICAL"}], "documents": [{"path": "2025/225C1629/8DF9E6C891A17EFCBB495FC63F9C7982DA9D8429C2BCBDA248C9DD77B85D97C3.pdf", "accessible": true, "nom_fichier": "225C1629.pdf"}, {"path": "2025/225C1629/33D3BD53F5D38563AD13D90148C74AEAC768A8F81A688059898AA65F5A47DE4C.pdf", "accessible": true, "nom_fichier": "225C162900.pdf"}, {"path": "2025/225C1629/59C67C4ABD2FFBA7CC459314FCBB3FA821EDE9BCAF1FD2A34CEB2F4066BEDA7A.pdf", "accessible": true, "nom_fichier": "225C162901.pdf"}, {"path": "2025/225C1629/54EB5C5BF108163EDA8F96E96EE3C2119807F6203E1D2AE8F0467F60276B30E9.pdf", "accessible": true, "nom_fichier": "225C162902.pdf"}, {"path": "2025/225C1629/6206DAC040E5C9AB7D18454D662BD625EA8E705F4B88F47820A7663C4490697D.pdf", "accessible": true, "nom_fichier": "225C162903.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-11-28T11:04:05.214804+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.209835+00
38	38	2026-05-19 14:23:12.237767+00	filing_amf	BDIF note d'information OPAS — visée: ALTAMIR (numero 225C1529)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1529/B5E5B14DB09B63248AD314DE0677266181D86CE9711A330BBDDE64135A76DED8.pdf	{"numero": "225C1529", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003545", "raison_sociale": "ALTAMIR"}, {"role": "Initiateur", "jeton": "RS00005821", "raison_sociale": "AMBOISE SAS"}], "documents": [{"path": "2025/225C1529/B5E5B14DB09B63248AD314DE0677266181D86CE9711A330BBDDE64135A76DED8.pdf", "accessible": true, "nom_fichier": "225C1529.pdf"}, {"path": "2025/225C1529/664F0718D82AECC22A0383F7C96085EE0628EE3A636BB0E6355D77BEC5A90B28.pdf", "accessible": true, "nom_fichier": "225C152900.pdf"}, {"path": "2025/225C1529/45C4EB8CC6B1B2D2B47429CE70F22E9D4E00EEF8729696444CF73AEEAAE55522.pdf", "accessible": true, "nom_fichier": "225C152901.pdf"}, {"path": "2025/225C1529/1FA9A3262B75AB3700FCE3E5BA63E17F9132DB7E4207C2A36A2C3FE8A2AC1E10.pdf", "accessible": true, "nom_fichier": "225C152902.pdf"}, {"path": "2025/225C1529/CAD9D5AA00E77FBFDDA7684EC74AC77B7D3959C40DCD97D54CD5F3DE56F23C42.pdf", "accessible": true, "nom_fichier": "225C152903.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-11-28T11:32:05.128036+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.23636+00
39	39	2026-05-19 14:23:12.2688+00	filing_amf	BDIF note d'information OPR — visée: TRONIC'S MICROSYSTEMS S.A. (numero 225C1507)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1507/E301EE3EF6B37DFAD4272EF1E160CA1E5832EADBF8D9B6387733A97822810066.pdf	{"numero": "225C1507", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005911", "raison_sociale": "TRONIC'S MICROSYSTEMS S.A."}, {"role": "Initiateur", "jeton": "RS00007557", "raison_sociale": "TDK ELECTRONICS AG"}], "documents": [{"path": "2025/225C1507/E301EE3EF6B37DFAD4272EF1E160CA1E5832EADBF8D9B6387733A97822810066.pdf", "accessible": true, "nom_fichier": "225C1507.pdf"}, {"path": "2025/225C1507/9F5562E73A80495BAE992A185180EB5D338684DE273ACA29E4BAE3379A8B2E4D.pdf", "accessible": true, "nom_fichier": "225C150700.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-09-09T15:36:22.232564+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.267021+00
40	40	2026-05-19 14:23:12.295813+00	filing_amf	BDIF note d'information OPAS — visée: AGROGENERATION (numero 225C1439)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1439/24F7E7C9EB30188B5FD0914078F16AB748E20D5EE7649132863B135FE4017D31.pdf	{"numero": "225C1439", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005064", "raison_sociale": "AGROGENERATION"}], "documents": [{"path": "2025/225C1439/24F7E7C9EB30188B5FD0914078F16AB748E20D5EE7649132863B135FE4017D31.pdf", "accessible": true, "nom_fichier": "225C1439.pdf"}, {"path": "2025/225C1439/069CE223115C4D35F0C172C045200E251ECD46C43E76D9CDF8E04E01C2BDD055.pdf", "accessible": true, "nom_fichier": "225C143900.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-08-26T17:10:06.016639+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.294252+00
41	41	2026-05-19 14:23:12.323436+00	filing_amf	BDIF note d'information OPAS — visée: AGROGENERATION (numero 225C1404)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1404/E8EEC4E35E2DEFE94F731224C1A87EB6BB09862E30C84AA012002CD5C640C19B.pdf	{"numero": "225C1404", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005064", "raison_sociale": "AGROGENERATION"}], "documents": [{"path": "2025/225C1404/E8EEC4E35E2DEFE94F731224C1A87EB6BB09862E30C84AA012002CD5C640C19B.pdf", "accessible": true, "nom_fichier": "225C1404.pdf"}, {"path": "2025/225C1404/FF475C89C4EF2B6657A1EFDC639A2958300AB7A4670E9F0D2CC903E813EB9139.pdf", "accessible": true, "nom_fichier": "225C140400.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-08-18T17:14:05.339088+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.321864+00
42	42	2026-05-19 14:23:12.355731+00	filing_amf	BDIF note d'information OPAS — visée: AMPLITUDE SURGICAL (numero 225C1285)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1285/AC0DAB36744D4ABF9AB5BE55149059EBF6F4932616FDD31223CFA13D250D0E81.pdf	{"numero": "225C1285", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006019", "raison_sociale": "AMPLITUDE SURGICAL"}], "documents": [{"path": "2025/225C1285/AC0DAB36744D4ABF9AB5BE55149059EBF6F4932616FDD31223CFA13D250D0E81.pdf", "accessible": true, "nom_fichier": "225C1285.pdf"}, {"path": "2025/225C1285/4FDBE555DD6B627143F3DDCA2CBD3B3322BDFAD74F8A791EF4B7768540E85FC4.pdf", "accessible": true, "nom_fichier": "225C128500.pdf"}, {"path": "2025/225C1285/F25581C26A1F520DAA34DF38EB1234658D072A480590704DF71D05FE292DDAA8.pdf", "accessible": true, "nom_fichier": "225C128501.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-07-30T16:46:05.323490+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.354277+00
43	43	2026-05-19 14:23:12.378076+00	filing_amf	BDIF note d'information OPA — visée: VOGO (numero 225C1258)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1258/66D00BC0E7AD03BD0F4A7BA4651F295DA8870150DFAB9075D707785B11973CF9.pdf	{"numero": "225C1258", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006663", "raison_sociale": "VOGO"}, {"role": "Initiateur", "jeton": "RS00006263", "raison_sociale": "ABEO"}], "documents": [{"path": "2025/225C1258/66D00BC0E7AD03BD0F4A7BA4651F295DA8870150DFAB9075D707785B11973CF9.pdf", "accessible": true, "nom_fichier": "225C1258.pdf"}, {"path": "2025/225C1258/424B9DFE7AE5E9309CEE3E45125B3BD4D47C5E996D662FE7D224C86535EA1A66.pdf", "accessible": true, "nom_fichier": "225C125800.pdf"}, {"path": "2025/225C1258/20C8F5D5003DDA42A6DBA8AD32942C4F968AF796797E495342354C5A9C23D7E6.pdf", "accessible": true, "nom_fichier": "225C125801.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPA", "OPE"], "date_information": null, "date_publication": "2025-11-28T12:28:04.740535+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.3765+00
44	44	2026-05-19 14:23:12.401621+00	filing_amf	BDIF note d'information OPR — visée: GROUPE ETPO SA (numero 225C1227)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1227/8E52F125753476B79E285A529935605690E7CDC62F9935FF2126E850B7197FCA.pdf	{"numero": "225C1227", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00002101", "raison_sociale": "GROUPE ETPO SA"}, {"role": "Initiateur", "jeton": "RS00008064", "raison_sociale": "GROUPE SPIE BATIGNOLLES SAS"}], "documents": [{"path": "2025/225C1227/8E52F125753476B79E285A529935605690E7CDC62F9935FF2126E850B7197FCA.pdf", "accessible": true, "nom_fichier": "225C1227.pdf"}, {"path": "2025/225C1227/8042DA8C637431EB95D96C207BB9EB700E0179FC3E31BB6127997C41D001FBD5.pdf", "accessible": true, "nom_fichier": "225C122700.pdf"}, {"path": "2025/225C1227/E6EF3DF74139612781966FAD438F2190D9E282AA5A8DAF28E542E50C4A4B0773.pdf", "accessible": true, "nom_fichier": "225C122701.pdf"}, {"path": "2025/225C1227/125FED29977988BD31C36373FA0A4AD816D2ABB3DE8621AC1E6128C9C0C84973.pdf", "accessible": true, "nom_fichier": "225C122702.pdf"}, {"path": "2025/225C1227/6F31BC30FA7608954C4261F86D30C8782DDC49D077B0B90C9C4640326011B048.pdf", "accessible": true, "nom_fichier": "225C122703.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-07-18T10:07:20.519942+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.398899+00
45	45	2026-05-19 14:23:12.426572+00	filing_amf	BDIF note d'information OPAS — visée: ALTAMIR (numero 225C1154)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1154/C9793687BB098BD663033E6439917178912A6215D9BCE88CC89765EDA50536D9.pdf	{"numero": "225C1154", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003545", "raison_sociale": "ALTAMIR"}, {"role": "Initiateur", "jeton": "RS00005821", "raison_sociale": "AMBOISE SAS"}], "documents": [{"path": "2025/225C1154/C9793687BB098BD663033E6439917178912A6215D9BCE88CC89765EDA50536D9.pdf", "accessible": true, "nom_fichier": "225C1154.pdf"}, {"path": "2025/225C1154/78B83AB59379A58AD81907691888A769135F86790C0A7CACB14CEB1FEDCF39EF.pdf", "accessible": true, "nom_fichier": "225C115400.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-07-04T17:52:05.653374+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.42513+00
361	362	2026-05-19 16:22:46.058981+00	filing_bafin	BaFin Angebotsunterlage — Bieter: PPF IM LTD, Zielgesellschaft: ProSiebenSat.1 Media SE (ref BAFIN-DE000PSM7770-20250604)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/PPF_IM_LTD.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE000PSM7770-20250604", "deal_type": "opa_volontaire_parziale", "bieter_name": "PPF IM LTD", "target_isin": "DE000PSM7770", "target_name": "ProSiebenSat.1 Media SE", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/PPF_IM_LTD.html?nn=151388", "has_document": true, "is_amendment": false, "pdf_metadata": {"currency": "EUR", "offer_price": "7.00", "opening_date": null, "closing_date_est": null, "offer_type_from_pdf": "ERWERBSANGEBOT", "bieter_name_from_pdf": "UND IHRER", "target_name_from_pdf": null}, "offer_type_raw": "Teilerwerbsangebot", "veroeffentlichung_date": "2025-06-04"}	2026-05-19 16:22:46.055654+00
46	46	2026-05-19 14:23:12.452987+00	filing_amf	BDIF note d'information OPR — visée: BELIEVE (numero 225C1153)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1153/8D4F4D57519FB0DBC66686235B1CC114E7A7C3F0DF2FC2535D4ADE7E847BCC04.pdf	{"numero": "225C1153", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007301", "raison_sociale": "BELIEVE"}], "documents": [{"path": "2025/225C1153/8D4F4D57519FB0DBC66686235B1CC114E7A7C3F0DF2FC2535D4ADE7E847BCC04.pdf", "accessible": true, "nom_fichier": "225C1153.pdf"}, {"path": "2025/225C1153/3ED1679B0A6EA5D247FA2F2950180AA3ACA33D96D66C0EE9FFD1F9462BB3CA07.pdf", "accessible": true, "nom_fichier": "225C115300.pdf"}, {"path": "2025/225C1153/1AF02602AF5AB984039B07DC6514C0F78EC58FFEB54DD80F306575B6B92E6608.pdf", "accessible": true, "nom_fichier": "225C115301.pdf"}, {"path": "2025/225C1153/694AD3BFD466A9B681DB2C5CF1FA9B3351D16CF9CF832B533ADE306ADC2369AB.pdf", "accessible": true, "nom_fichier": "225C115302.pdf"}, {"path": "2025/225C1153/B044F3334D4CE752FC67228BF3E91482985A3C54E3BF523CDD8ACC22D8EFE043.pdf", "accessible": true, "nom_fichier": "225C115303.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-11-28T11:38:04.966653+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.451583+00
47	47	2026-05-19 14:23:12.476904+00	filing_amf	BDIF note d'information OPA — visée: ELECTRICITE ET EAUX DE MADAGASCAR (numero 225C1139)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1139/8BBACCFF5CC17C6941B15D31D95987856AAB9CD9E5EFEC4199D8BFA0098A9D2B.pdf	{"numero": "225C1139", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001534", "raison_sociale": "ELECTRICITE ET EAUX DE MADAGASCAR"}], "documents": [{"path": "2025/225C1139/8BBACCFF5CC17C6941B15D31D95987856AAB9CD9E5EFEC4199D8BFA0098A9D2B.pdf", "accessible": true, "nom_fichier": "225C1139.pdf"}, {"path": "2025/225C1139/C0694040C429B8DF5B1C6549928280D1D38B541B9705A109CE010086EECF96A1.pdf", "accessible": true, "nom_fichier": "225C113900.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2025-07-02T11:04:04.941117+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.475486+00
48	48	2026-05-19 14:23:12.499204+00	filing_amf	BDIF note d'information OPAS — visée: ALTAMIR (numero 225C1003)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C1003/05ABE9DBA29A5ECF05C9F78B5AE905C73FB41BD48C6980F685BFE28737829D77.pdf	{"numero": "225C1003", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00003545", "raison_sociale": "ALTAMIR"}, {"role": "Initiateur", "jeton": "RS00005821", "raison_sociale": "AMBOISE SAS"}], "documents": [{"path": "2025/225C1003/05ABE9DBA29A5ECF05C9F78B5AE905C73FB41BD48C6980F685BFE28737829D77.pdf", "accessible": true, "nom_fichier": "225C1003.pdf"}, {"path": "2025/225C1003/53D791546DD15265ABC89869A87CE27A97A0EF8D7113FC5225C3D83BF3C72331.pdf", "accessible": true, "nom_fichier": "225C100300.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-06-16T15:42:06.739816+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.497229+00
49	49	2026-05-19 14:23:12.526051+00	filing_amf	BDIF note d'information OPR — visée: GROUPE ETPO SA (numero 225C0995)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0995/89F80B88B4C39CB8BE6C6E00CE15DED65CC13580E802F7616A1FF8EB217C8E76.pdf	{"numero": "225C0995", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00002101", "raison_sociale": "GROUPE ETPO SA"}, {"role": "Initiateur", "jeton": "RS00008064", "raison_sociale": "GROUPE SPIE BATIGNOLLES SAS"}], "documents": [{"path": "2025/225C0995/89F80B88B4C39CB8BE6C6E00CE15DED65CC13580E802F7616A1FF8EB217C8E76.pdf", "accessible": true, "nom_fichier": "225C0995.pdf"}, {"path": "2025/225C0995/AC9F86D9390B2AA59824F202368DB8AECE93A45B9C64B39793B08D84E3DD485D.pdf", "accessible": true, "nom_fichier": "225C099500.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-06-13T15:28:05.493412+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.524803+00
50	50	2026-05-19 14:23:12.556482+00	filing_amf	BDIF note d'information OPR — visée: TARKETT S.A. (numero 225C0943)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0943/2766C94AB6689E31301176B6AB33C47F5BFA24283DFC719261629B63E795CE80.pdf	{"numero": "225C0943", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00004395", "raison_sociale": "TARKETT S.A."}], "documents": [{"path": "2025/225C0943/2766C94AB6689E31301176B6AB33C47F5BFA24283DFC719261629B63E795CE80.pdf", "accessible": true, "nom_fichier": "225C0943.pdf"}, {"path": "2025/225C0943/A96918B9C43BE9E169D6B1BB1E62EFCFDE70771790C1AAEAB3207A680546B42D.pdf", "accessible": true, "nom_fichier": "225C094300.pdf"}, {"path": "2025/225C0943/0FD740DCAE6A1568FC8DC71B5EB798191C3FE214F8207C5B28FBE2EB886352F6.pdf", "accessible": true, "nom_fichier": "225C094301.pdf"}, {"path": "2025/225C0943/A17F47C435C3B70922F23388E97C10FC5B2212F224115255783D948DFA4CEA62.pdf", "accessible": true, "nom_fichier": "225C094302.pdf"}, {"path": "2025/225C0943/6E0DB6EDA8C13CD8719FDEAD75CD9945A7FA273C011E9A24CB32BFADD428A7ED.pdf", "accessible": true, "nom_fichier": "225C094303.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-06-06T16:04:09.517410+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.555246+00
51	51	2026-05-19 14:23:12.79877+00	filing_amf	BDIF note d'information OPA — visée: VERALLIA (numero 225C0929)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0929/F0920AB04DC74434B52DD0FE7CB8BD0D0848FBCA912571968BD0585BAF6E0DA4.pdf	{"numero": "225C0929", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005230", "raison_sociale": "VERALLIA"}], "documents": [{"path": "2025/225C0929/F0920AB04DC74434B52DD0FE7CB8BD0D0848FBCA912571968BD0585BAF6E0DA4.pdf", "accessible": true, "nom_fichier": "225C0929.pdf"}, {"path": "2025/225C0929/26A2E7D07DEEA627D2E00BBA0858F7CE583DEFCAD3DF67355EB6AB7AB4B794CD.pdf", "accessible": true, "nom_fichier": "225C092900.pdf"}, {"path": "2025/225C0929/B58961131B07E92E283A2002B7AF8D73E89E6178FBEBAA0FC8674C3FDB10EBA7.pdf", "accessible": true, "nom_fichier": "225C092901.pdf"}, {"path": "2025/225C0929/997345C48EA356E175468B3164D21C409DD0521E37166BF49F2AE18D5F96D5ED.pdf", "accessible": true, "nom_fichier": "225C092902.pdf"}, {"path": "2025/225C0929/284AF5354134531A49E4B17B84A7DC4607604F21A0F239424F9E6B2A7617D39D.pdf", "accessible": true, "nom_fichier": "225C092903.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2025-11-28T11:50:06.198913+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.796878+00
52	52	2026-05-19 14:23:12.826564+00	filing_amf	BDIF note d'information OPAS — visée: M2I (numero 225C0921)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0921/598AEEE4C8C8BA22E6E8F10899BF9587CAB180EDE7FD1370A2FC31000A928867.pdf	{"numero": "225C0921", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006453", "raison_sociale": "M2I"}, {"role": "Initiateur", "jeton": "RS00008346", "raison_sociale": "ABILWAYS"}], "documents": [{"path": "2025/225C0921/598AEEE4C8C8BA22E6E8F10899BF9587CAB180EDE7FD1370A2FC31000A928867.pdf", "accessible": true, "nom_fichier": "225C0921.pdf"}, {"path": "2025/225C0921/9A2E08060931AD51C8096901B068490CF7D45DCEB8DAEEE4ADCAA4EBFFD64448.pdf", "accessible": true, "nom_fichier": "225C092100.pdf"}, {"path": "2025/225C0921/3EBE828830F1E7B2B1B84E89783BAC80C99E92BC6161B6EA59B4D021D17DE991.pdf", "accessible": true, "nom_fichier": "225C092101.pdf"}, {"path": "2025/225C0921/3AFB054045C21DAAF7D67BE690879D9F4EFC14A402EB270FDD2DC5D2F8D16634.pdf", "accessible": true, "nom_fichier": "225C092102.pdf"}, {"path": "2025/225C0921/A144ED5AE09E939FBE1193CA3DF91E22B9515A0FDC834BEBEF30F40056754F75.pdf", "accessible": true, "nom_fichier": "225C092103.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-06-06T09:12:05.872608+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.824991+00
53	53	2026-05-19 14:23:12.846368+00	filing_amf	BDIF note d'information OPR — visée: BELIEVE (numero 225C0920)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0920/EFA14EF47EA8E982099F77768E6D5DB5982A1FB2DD38ADF653B80696FF46ED09.pdf	{"numero": "225C0920", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00007301", "raison_sociale": "BELIEVE"}], "documents": [{"path": "2025/225C0920/EFA14EF47EA8E982099F77768E6D5DB5982A1FB2DD38ADF653B80696FF46ED09.pdf", "accessible": true, "nom_fichier": "225C0920.pdf"}, {"path": "2025/225C0920/687A00EC0F8F9852DB99F931A1DE80A0BDA3602102F747A22FFA6E77CD482376.pdf", "accessible": true, "nom_fichier": "225C092000.pdf"}, {"path": "2025/225C0920/D02284CB5882C6EAE8C10B5FB47B6C7691F3E0FAEFEAA26964E152CAC1D8A93B.pdf", "accessible": true, "nom_fichier": "225C092001.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-06-05T15:12:05.138323+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.844884+00
54	54	2026-05-19 14:23:12.871677+00	filing_amf	BDIF note d'information OPAS — visée: UNIBEL (numero 225C0845)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0845/5959CDC36EEA75D9BB16F9817DF6C7314CE63D89790E33FEB1DA8C70DFF12CC7.pdf	{"numero": "225C0845", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001324", "raison_sociale": "UNIBEL"}], "documents": [{"path": "2025/225C0845/5959CDC36EEA75D9BB16F9817DF6C7314CE63D89790E33FEB1DA8C70DFF12CC7.pdf", "accessible": true, "nom_fichier": "225C0845.pdf"}, {"path": "2025/225C0845/F6B854E2EA4C8114C16C06AF44CBC94EE58E8DB8EC650DBB2A5638BFDD24E0F2.pdf", "accessible": true, "nom_fichier": "225C084500.pdf"}, {"path": "2025/225C0845/F606865ACB00FE0E6CC31A002E6E0599B5B46907911CE7A6F657E227DC6CA32A.pdf", "accessible": true, "nom_fichier": "225C084501.pdf"}, {"path": "2025/225C0845/DDD1B0FCE9002020B519FCE22F7F36596C2760DD6CE0C7DC71819327BF24388F.pdf", "accessible": true, "nom_fichier": "225C084502.pdf"}, {"path": "2025/225C0845/328E75E90EE85D78DC84BDFDD3316A7568D85112FE531D756987E9E454AEBA4A.pdf", "accessible": true, "nom_fichier": "225C084503.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-05-26T10:50:06.840415+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.870305+00
55	55	2026-05-19 14:23:12.897117+00	filing_amf	BDIF note d'information OPR — visée: GROUPE ETPO SA (numero 225C0838)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0838/7C5773E08924691DD74132E2C661DB3DE388B66A8E0BB41F5FADB7D71B0D3202.pdf	{"numero": "225C0838", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00002101", "raison_sociale": "GROUPE ETPO SA"}, {"role": "Initiateur", "jeton": "RS00008064", "raison_sociale": "GROUPE SPIE BATIGNOLLES SAS"}], "documents": [{"path": "2025/225C0838/7C5773E08924691DD74132E2C661DB3DE388B66A8E0BB41F5FADB7D71B0D3202.pdf", "accessible": true, "nom_fichier": "225C0838.pdf"}, {"path": "2025/225C0838/8CC64886C10A163C01A011243CC8F371C7001F252AEDBC6CBA572A45A9D50B19.pdf", "accessible": true, "nom_fichier": "225C083800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-05-22T16:20:05.159967+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.895311+00
56	56	2026-05-19 14:23:12.923018+00	filing_amf	BDIF note d'information OPR — visée: FINANCIERE MONCEY (numero 225C0741)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0741/17E366B209E9E2ED0180EB9A7C7B00839735621223DF35947F824CB4EFE1E12D.pdf	{"numero": "225C0741", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001419", "raison_sociale": "FINANCIERE MONCEY"}, {"role": "Initiateur", "jeton": "RS00000987", "raison_sociale": "BOLLORE SE"}], "documents": [{"path": "2025/225C0741/17E366B209E9E2ED0180EB9A7C7B00839735621223DF35947F824CB4EFE1E12D.pdf", "accessible": true, "nom_fichier": "225C0741.pdf"}, {"path": "2025/225C0741/2EE87FB9C753D96753E1E5FBFBF1BEBF1FDA154F5879945E1D6191ABD4E56C58.pdf", "accessible": true, "nom_fichier": "225C074100.pdf"}, {"path": "2025/225C0741/6869504BF61AE54B120F517D53241E8CDAD3045EE1FFEA9968BA9D62E2979B45.pdf", "accessible": true, "nom_fichier": "225C074101.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-05-05T09:32:09.840634+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.921746+00
57	57	2026-05-19 14:23:12.950207+00	filing_amf	BDIF note d'information OPR — visée: COMPAGNIE DU CAMBODGE (numero 225C0740)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0740/1283751425D68B1A5DF96C9EC10E51976B0C0CEE68842E85A9393EC463C78975.pdf	{"numero": "225C0740", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001364", "raison_sociale": "COMPAGNIE DU CAMBODGE"}, {"role": "Initiateur", "jeton": "RS00000987", "raison_sociale": "BOLLORE SE"}], "documents": [{"path": "2025/225C0740/1283751425D68B1A5DF96C9EC10E51976B0C0CEE68842E85A9393EC463C78975.pdf", "accessible": true, "nom_fichier": "225C0740.pdf"}, {"path": "2025/225C0740/AB74D7B64C0197ED4E43418DB1B0D6B01AD6BA3D706C639B918DB194D1361450.pdf", "accessible": true, "nom_fichier": "225C074000.pdf"}, {"path": "2025/225C0740/98698EC392BD475B7E05463B440106A8368629668EA7F709BBEE7D2CFB85582B.pdf", "accessible": true, "nom_fichier": "225C074001.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-05-05T09:32:14.093650+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.948083+00
58	58	2026-05-19 14:23:12.974961+00	filing_amf	BDIF note d'information OPR — visée: SOCIETE INDUSTRIELLE ET FINANCIERE DE L'ARTOIS (numero 225C0739)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0739/49EDABB0E59E6DFB2185881C48662DD85049EDD259627F0F16D69C6A9FFDF6A4.pdf	{"numero": "225C0739", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00001429", "raison_sociale": "SOCIETE INDUSTRIELLE ET FINANCIERE DE L'ARTOIS"}, {"role": "Initiateur", "jeton": "RS00000987", "raison_sociale": "BOLLORE SE"}], "documents": [{"path": "2025/225C0739/49EDABB0E59E6DFB2185881C48662DD85049EDD259627F0F16D69C6A9FFDF6A4.pdf", "accessible": true, "nom_fichier": "225C0739.pdf"}, {"path": "2025/225C0739/8B2B361D2CF00AFDA16A3C28FB55CCE62510D5CA25EA189E000EF5699B236CFF.pdf", "accessible": true, "nom_fichier": "225C073900.pdf"}, {"path": "2025/225C0739/5B0E9A92DCD0FD263A1107C111635A9B66CDCF6F335FB571434675A6A3954278.pdf", "accessible": true, "nom_fichier": "225C073901.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "Decisions"], "types_operation": ["OPR"], "date_information": null, "date_publication": "2025-11-28T11:14:05.166925+01:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.973616+00
59	59	2026-05-19 14:23:13.001121+00	filing_amf	BDIF note d'information OPAS — visée: M2I (numero 225C0725)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0725/686E4EA41EA6F49A0DDF69C4D06BBD4A0CE2D1FB6D7F3A165F8BB9E22B2AABE2.pdf	{"numero": "225C0725", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00006453", "raison_sociale": "M2I"}, {"role": "Initiateur", "jeton": "RS00008346", "raison_sociale": "ABILWAYS"}], "documents": [{"path": "2025/225C0725/686E4EA41EA6F49A0DDF69C4D06BBD4A0CE2D1FB6D7F3A165F8BB9E22B2AABE2.pdf", "accessible": true, "nom_fichier": "225C0725.pdf"}, {"path": "2025/225C0725/3BEA91AF05563A7F56958790A25463A0FCE8E01359027F1FD30567D1FD733686.pdf", "accessible": true, "nom_fichier": "225C072500.pdf"}, {"path": "2025/225C0725/20ED108DC53F2BF18B3EBF98634106DE5C22EF6B7575DCE2FADBBED2B8BEF5E8.pdf", "accessible": true, "nom_fichier": "225C072501.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPAS"], "date_information": null, "date_publication": "2025-06-06T09:14:05.698816+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:12.998852+00
60	60	2026-05-19 14:23:13.028782+00	filing_amf	BDIF note d'information OPA — visée: VERALLIA (numero 225C0708)	https://bdif.amf-france.org/back/api/v1/documents/2025/225C0708/307129575A270937D25873228E87EF688B894D56B00E9385B4121A76FCC35177.pdf	{"numero": "225C0708", "source": "bdif", "domaine": "DOIF", "societes": [{"role": "SocieteVisee", "jeton": "RS00005230", "raison_sociale": "VERALLIA"}], "documents": [{"path": "2025/225C0708/307129575A270937D25873228E87EF688B894D56B00E9385B4121A76FCC35177.pdf", "accessible": true, "nom_fichier": "225C0708.pdf"}, {"path": "2025/225C0708/ACF88250E68514815796696D415A08F8E6D3302AC518A231BEB4802BDC8CDC20.pdf", "accessible": true, "nom_fichier": "225C070800.pdf"}], "has_document": true, "types_document": ["NotesEtAutresInformations", "DepotOffre"], "types_operation": ["OPA"], "date_information": null, "date_publication": "2025-06-06T08:40:05.556397+02:00", "types_information": ["OPA"]}	2026-05-19 14:23:13.026591+00
325	326	2026-05-19 14:41:51.631447+00	filing_consob	Consob documento d'offerta — offerente: Banca CF+ Credito Fondiario Spa, visée: Banca Sistema Spa (ref CONSOB-opa_bancasistema_20260511)	https://www.consob.it/documents/11973/11173223/opa_bancasistema_20260511.pdf/6a2eb96e-07be-acdb-bce8-4c9718262999?version=1.0&t=1777986457850&download=false	{"source": "consob_documenti_opa", "deal_type": "opas", "consob_ref": "CONSOB-opa_bancasistema_20260511", "period_end": "2026-06-12", "description": "Offerta pubblica di acquisto e scambio obbligatoria totalitaria promossa da Banca CF+ Credito Fondiario Spa su azioni emesse da Banca Sistema Spa . Il corrispettivo offerto è pari a 1,89 euro per ciascuna azione portata in adesione all'offerta, rappresentato da: (a) 1,432 euro in denaro; e (b) 0,458 euro, per ciascuna azione portata in adesione all'offerta, da pagarsi mediante l'attribuzione di un massimo di 23 azioni Kruso Kapital Spa (controllata da Banca Sistema) previo frazionamento.", "page_number": 1, "target_name": "Banca Sistema Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "1.89", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "OFFERENTE", "offerente_name_from_pdf": "Banca C.F"}, "period_start": "2026-05-11", "offerente_name": "Banca CF+ Credito Fondiario Spa", "additional_links": []}	2026-05-19 14:41:51.620512+00
326	327	2026-05-19 14:41:52.681771+00	filing_consob	Consob documento d'offerta — offerente: Cir Spa, visée: ? (ref CONSOB-opa_cir_20260427)	https://www.consob.it/documents/11973/11173223/opa_cir_20260427.pdf/d7e8402c-5a89-5a9a-3e0b-62f4dfc18e7c?version=1.0&t=1778228094244&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_volontaire_parziale", "consob_ref": "CONSOB-opa_cir_20260427", "period_end": "2026-05-18", "description": "Offerta pubblica di acquisto volontaria parziale promossa da Cir Spa su un massimo di 50.0000.000 azioni emesse dalla stessa Cir. Il corrispettivo unitario è pari ad 0,68 euro per azione", "page_number": 1, "target_name": null, "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "0.68", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "CIR S.p.A.-Compagnie Industriali Riunite", "offerente_name_from_pdf": "ED EMITTENTE"}, "period_start": "2026-04-27", "offerente_name": "Cir Spa", "additional_links": []}	2026-05-19 14:41:52.680171+00
327	328	2026-05-19 14:41:54.655107+00	filing_consob	Consob documento d'offerta — offerente: Oep Danzig BidCo Spa, visée: Digital Value Spa (ref CONSOB-opa_danzic_20260424)	https://www.consob.it/documents/11973/11173223/opa_danzic_20260424.pdf/39710032-6eba-f885-0d5d-14f0c471aaa7?version=1.0&t=1776951574254&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_obligatoire", "consob_ref": "CONSOB-opa_danzic_20260424", "period_end": "2026-05-15", "description": "Offerta pubblica di acquisto obbligatoria, promossa da Oep Danzig BidCo Spa , su azioni Digital Value Spa . Il corrispettivo è pari ad 29,00 euro cum dividendo.", "page_number": 1, "target_name": "Digital Value Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "29.00", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "Digital Value S.p.A", "offerente_name_from_pdf": "OEP Danzig BidCo S.p.A"}, "period_start": "2026-04-24", "offerente_name": "Oep Danzig BidCo Spa", "additional_links": [{"url": "https://www.consob.it/documents/11973/11173223/opa_danzig_cs20260514.pdf/d40d44fc-6c89-73fe-c898-74ea00a78e67?version=1.0&t=1778831928368&download=false", "label": "Comunicato sulla proroga del periodo di adesione"}, {"url": "https://www.consob.it/documents/11973/11173223/opa_danzig_cs20260519.pdf/6b50637c-00bc-dee0-d383-d88fccc159ca?version=1.0&t=1779180242720&download=false", "label": "Comunicato sui risultati definitivi dell'offerta"}]}	2026-05-19 14:41:54.653175+00
328	329	2026-05-19 14:41:56.699245+00	filing_consob	Consob documento d'offerta — offerente: CPI Property Group Sa, visée: Next Re SIIQ Spa (ref CONSOB-opa_nextre_20260420)	https://www.consob.it/documents/11973/11173223/opa_nextre_20260420.pdf/21d78c73-9007-5f13-d370-61662d7e0b86?version=1.0&t=1776437533321&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_volontaire_totalitaria", "consob_ref": "CONSOB-opa_nextre_20260420", "period_end": "2026-05-15", "description": "Offerta pubblica di acquisto volontaria totalitaria promossa da CPI Property Group Sa , avente ad oggetto azioni emesse da Next Re SIIQ Spa . Il corrispettivo unitario offerto è pari a 3,00 euro cum dividendo .", "page_number": 1, "target_name": "Next Re SIIQ Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "3.00", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "e dell", "offerente_name_from_pdf": "CPI Property Group S.A"}, "period_start": "2026-04-20", "offerente_name": "CPI Property Group Sa", "additional_links": [{"url": "https://www.consob.it/documents/11973/11173223/opa_nextre_cs20260512.pdf/176ef100-53f1-06c5-c76c-f7993f28e103?version=1.0&t=1778676222893&download=false", "label": "Comunicato sul superamento della soglia del 90%"}]}	2026-05-19 14:41:56.697586+00
329	330	2026-05-19 14:41:58.117121+00	filing_consob	Consob documento d'offerta — offerente: Banco di Desio e della Brianza Spa, visée: Solutions Capital Management Sim Spa (ref CONSOB-opa_banco_desio_20260330)	https://www.consob.it/documents/11973/11173223/opa_banco_desio_20260330.pdf/07c7630b-2422-c466-f966-4a812e9410ae?version=1.0&t=1775034768682&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_volontaire_totalitaria", "consob_ref": "CONSOB-opa_banco_desio_20260330", "period_end": "2026-04-24", "description": "Offerta pubblica di acquisto volontaria totalitaria promossa da Banco di Desio e della Brianza Spa su azioni ordinarie emesse da Solutions Capital Management Sim Spa . Il corrispettivo offerto è di 4,61 euro per azione.", "page_number": 1, "target_name": "Solutions Capital Management Sim Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "4.61", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "GLI STRUMENTI FINANZIARI OGGETTO DELL", "offerente_name_from_pdf": "BANCO DI DESIO E DELLA BRIANZA S.P.A"}, "period_start": "2026-03-30", "offerente_name": "Banco di Desio e della Brianza Spa", "additional_links": [{"url": "https://www.consob.it/documents/11973/11173223/opa_banco_desio_cs20260422.pdf/dfa02a87-c0ea-a1f8-5bf3-249eee7ae72e?version=1.0&t=1776922586720&download=false", "label": "Comunicato sulla proroga condizionata del periodo di adesione"}, {"url": "https://www.consob.it/documents/11973/11173223/opa_banco_desio_cs20260427.pdf/98173b7d-8fdb-bb9b-6b50-369ade690c2d?version=1.0&t=1777447843899&download=false", "label": "Comunicato sui risultati definitivi dell'offerta"}]}	2026-05-19 14:41:58.115651+00
330	331	2026-05-19 14:41:58.948924+00	filing_consob	Consob documento d'offerta — offerente: Azúr as, visée: Ferretti Spa (ref CONSOB-opa_ferretti_20260316)	https://www.consob.it/documents/11973/11173223/opa_ferretti_20260316.pdf/08cdbfd3-2ef7-5a64-c6fa-82636ac7ad41?version=1.0&t=1773053920134&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_volontaire_parziale", "consob_ref": "CONSOB-opa_ferretti_20260316", "period_end": "2026-04-13", "description": "Offerta pubblica di acquisto volontaria parziale promossa, ai sensi dell'art. 102 del d.lgs. n. 58 del 1998, da Azúr as , su azioni di Ferretti Spa , ad un prezzo unitario di 3,50 euro.", "page_number": 1, "target_name": "Ferretti Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "3.50", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "Consulenti finanziari dell'Offerente", "offerente_name_from_pdf": "Salvo che il contesto non richieda diversamente"}, "period_start": "2026-03-16", "offerente_name": "Azúr as", "additional_links": []}	2026-05-19 14:41:58.947139+00
331	332	2026-05-19 14:42:00.621733+00	filing_consob	Consob documento d'offerta — offerente: ?, visée: Tinexta Spa (ref CONSOB-opa_Tinexta_20260223)	https://www.consob.it/documents/11973/11173223/opa_Tinexta_20260223.pdf/a1f842fa-0198-9f35-8d33-58831af87412?version=1.0&t=1771835796072&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_obligatoire", "consob_ref": "CONSOB-opa_Tinexta_20260223", "period_end": "2026-03-20", "description": "Offerta pubblica di acquisto obbligatoria totalitaria promossa da Zinc BidCo Spa , ai sensi degli articoli 102, 106, comma 1 e 109 del d.lgs. n. 58 del 1998, avente ad oggetto un massimo di 19.573.795 azioni emesse da Tinexta Spa , ad un corrispettivo unitario pari a 15,00 euro cum dividendo .", "page_number": 1, "target_name": "Tinexta Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "15.00", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "Tinexta S.p.A", "offerente_name_from_pdf": "Zinc BidCo S.p.A"}, "period_start": "2026-02-23", "offerente_name": null, "additional_links": [{"url": "https://www.consob.it/documents/11973/11173223/OPA+Tinexta+-+comunicato+del+24+marzo+2026.pdf/2e1ad766-8f91-e6f7-23a3-476881390188?version=1.0&t=1777360013271&download=false", "label": "Comunicato sui risultati definitivi dell’offerta"}, {"url": "https://www.consob.it/documents/11973/11173223/OPA+Tinexta+-+comunicato+del+10+aprile+2026.pdf/672fd29d-ba13-b38a-1ef3-47d3b0296f6f?version=1.0&t=1777360012414&download=false", "label": "Comunicato sui risultati definitivi a seguito della riapertura dei termini"}]}	2026-05-19 14:42:00.620218+00
332	333	2026-05-19 14:42:02.765082+00	filing_consob	Consob documento d'offerta — offerente: ?, visée: ? (ref CONSOB-opa_antares_20260216)	https://www.consob.it/documents/11973/11173223/opa_antares_20260216.pdf/3d16d01f-e8d0-32eb-6dad-b3aefab28c5f?version=1.0&t=1771247533790&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_obligatoire", "consob_ref": "CONSOB-opa_antares_20260216", "period_end": "2026-03-06", "description": "Offerta pubblica di acquisto obbligatoria totalitaria promossa, ai sensi degli articoli 102, 106, comma 1, e 109 del d.lgs. n. 58 del 1998, da Crane NXT Inspection and Tracking Technologies Spa , su azioni Antares Vision Spa . Il corrispettivo unitario è pari 5,00 euro cum dividendo.", "page_number": 1, "target_name": null, "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "5.00", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "Offerente", "offerente_name_from_pdf": "Crane NXT Inspection and Tracking Technologies S.p.A"}, "period_start": "2026-02-16", "offerente_name": null, "additional_links": [{"url": "https://www.consob.it/documents/11973/11173223/opa_antares_cs20260311.pdf/b59a5e08-7903-47da-eec1-de234d5ef98a?version=1.0&t=1776778999508&download=false", "label": "Comunicato sui risultati definitivi dell'offerta"}, {"url": "https://www.consob.it/documents/11973/11173223/opa_antares_cs20260324.pdf/85e03bad-9485-2d5e-3ce6-088973ca4cd6?version=1.0&t=1776779227416&download=false", "label": "Comunicato sui risultati definitivi a seguito della riapertura dei termini"}]}	2026-05-19 14:42:02.763663+00
333	334	2026-05-19 14:42:05.375778+00	filing_consob	Consob documento d'offerta — offerente: Lonvita Spa, visée: Health Italia Spa (ref CONSOB-opa_health_italia_20260409)	https://www.consob.it/documents/11973/11173223/opa_health_italia_20260409.pdf/63a6f544-5c05-5c36-e3f4-620d67ae7972?version=1.0&t=1770374793287&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_obligatoire", "consob_ref": "CONSOB-opa_health_italia_20260409", "period_end": "2026-03-06", "description": "Offerta pubblica di acquisto obbligatoria totalitaria promossa da Lonvita Spa , ai sensi degli articoli 102 e 106, comma 1 del d.lgs. n. 58 del 1998 e dell’art. 13 dello statuto di Health Italia S.p.A., su azioni Health Italia Spa . Il corrispettivo è pari a Euro 300,00 per ciascuna azione.", "page_number": 1, "target_name": "Health Italia Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "300.00", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "DALLE NEGOZIAZIONI SULL", "offerente_name_from_pdf": "Lonvita S.p.A"}, "period_start": "2026-02-09", "offerente_name": "Lonvita Spa", "additional_links": [{"url": "https://www.consob.it/documents/11973/11173223/opa_health_italia_cs20260305.pdf/072b1a10-bb42-ff7c-99ca-6f49bfc68bab?version=1.0&t=1772789103753&download=false", "label": "Comunicato relativo alla proroga del periodo di adesione dell'opa"}, {"url": "https://www.consob.it/documents/11973/11173223/opa_health_italia_cs20260309.pdf/cb28ee29-c26c-a0e6-4f62-7347208f9495?version=1.0&t=1773226954326&download=false", "label": "Comunicato sul superamento della soglia del 95% del capitale"}, {"url": "https://www.consob.it/documents/11973/11173223/opa_health_italia_cs20260316.pdf/b92c57c1-d18e-823b-19a6-022354dad54c?version=1.0&t=1773740687133&download=false", "label": "Comunicato sui risultati definitivi dell'offerta"}]}	2026-05-19 14:42:05.37448+00
334	335	2026-05-19 14:42:06.388618+00	filing_consob	Consob documento d'offerta — offerente: Banca CF+ Credito Fondiario Spa, visée: Banca Sistema Spa (ref CONSOB-opas_Banca_Sistema_20260116)	https://www.consob.it/documents/11973/11173223/opas_Banca_Sistema_20260116.pdf/35910c2c-1d58-445e-c93c-a297cb5f3557?version=1.0&t=1768571745569&download=false	{"source": "consob_documenti_opa", "deal_type": "opas", "consob_ref": "CONSOB-opas_Banca_Sistema_20260116", "period_end": "2026-02-27", "description": "Offerta pubblica di acquisto e scambio volontaria (Opas) promossa (ai sensi degli artt. 102 e ss. del d.lgs. n. 58 del 1998), da Banca CF+ Credito Fondiario Spa sulla totalità delle azioni ordinarie emesse da Banca Sistema Spa . Per ciascuna azione portata in adesione, Banca CF+ riconoscerà un corrispettivo complessivo pari a un massimo di 1,80 euro rappresentato da: 1,382 euro in denaro; un massimo di 0,418 euro da pagarsi mediante l’attribuzione di 21 azioni Kruso Kapital Spa.", "page_number": 1, "target_name": "Banca Sistema Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "1.80", "opening_date": "2026-01-26", "official_visa": null, "closing_date_est": "2026-02-27", "announcement_date": null, "target_name_from_pdf": "OFFERENTE", "offerente_name_from_pdf": "Banca C.F"}, "period_start": "2026-01-16", "offerente_name": "Banca CF+ Credito Fondiario Spa", "additional_links": [{"url": "https://www.consob.it/documents/11973/11173223/opas_Banca_Sistema_cs_20260123.pdf/c96c05d4-7a27-edf6-f5d7-c9c302c5d3fc?version=1.0&t=1769426996229&download=false", "label": "Comunicato del Consiglio di Amministrazione"}, {"url": "https://www.consob.it/documents/11973/11173223/opas_banca_sistema_cs20260218.pdf/9afb7f99-6c98-abbd-7a8d-76a570fc621b?version=1.0&t=1771489365566&download=false", "label": "Comunicato di incremento del corrispettivo"}, {"url": "https://www.consob.it/documents/11973/11173223/opas_banca_sistema_cs20260304.pdf/a1dda227-09c6-0446-a82e-991ff5e74fb0?version=1.0&t=1772697374770&download=false", "label": "Comunicato sui risultati definitivi dell'opa"}, {"url": "https://www.consob.it/documents/11973/11173223/opas_banca_sistema_cs20260318.pdf/94ad8d82-bcbf-8a37-1249-16985ff88df1?version=1.0&t=1773909478870&download=false", "label": "Comunicati risultati definitivi della riapertura dei termini dell’opas"}]}	2026-05-19 14:42:06.385427+00
335	336	2026-05-19 14:42:07.436819+00	filing_consob	Consob documento d'offerta — offerente: Ebidco srl, visée: Eles Semiconductor Equipment Spa (ref CONSOB-opa_eles_20260105)	https://www.consob.it/documents/11973/9797550/opa_eles_20260105.pdf/18a730f7-de22-6923-1c48-b61f81cba606?version=1.0&t=1766135766099&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_obligatoire", "consob_ref": "CONSOB-opa_eles_20260105", "period_end": "2026-02-06", "description": "Offerta pubblica di acquisto obbligatoria totalitaria, promossa ai sensi degli artt. 102 e seguenti del d. lgs. n. 58 del 1998, da Ebidco srl, su azioni Eles Semiconductor Equipment Spa . Il corrispettivo è pari a Euro 2,65 per ciascuna azione.", "page_number": 1, "target_name": "Eles Semiconductor Equipment Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "2.65", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "E PARERE DEGLI AMMINISTRATORI INDIPENDENTI............. 39", "offerente_name_from_pdf": "EBIDCO S.R.L"}, "period_start": "2026-01-05", "offerente_name": "Ebidco srl", "additional_links": [{"url": "https://www.consob.it/documents/11973/9797550/opa_eles_cs20251218.pdf/7374191b-2b84-998c-c69a-b5b56b32e4c8?version=1.0&t=1766138309630&download=false", "label": "Comunicato sull'incremento del corrispettivo"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_eles_cs20251219.pdf/13120512-c21d-a276-ebfc-cda5d2e48528?version=1.0&t=1766424622797&download=false", "label": "Comunicato dell’emittente e il parere degli amministratori indipendenti"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_eles_cs20251224.pdf/2fef3b7e-5c5f-3262-c45f-e74193b13309?version=1.0&t=1767343955167&download=false", "label": "Comunicato sull'incremento del corrispettivo"}, {"url": "https://www.consob.it/documents/11973/11173223/opa_eles_cs20260203.pdf/b8767cef-a275-3d3d-f918-a0c87b3067ee?version=1.0&t=1771248050222&download=false", "label": "Comunicato sulla proroga periodo di adesione"}, {"url": "https://www.consob.it/documents/11973/11173223/opa_eles_cs_20260303.pdf/d992812d-64aa-2487-ecc1-b459d0e61baa?version=1.0&t=1772697119051&download=false", "label": "Comunicato sui risultati definitivi dell’opa"}, {"url": "https://www.consob.it/documents/11973/11173223/opa_eles_cs20260312.pdf/024a4ebc-1f80-57cc-e47f-9fee0036e7e6?version=1.0&t=1773674741037&download=false", "label": "Supplemento al documento d'offerta"}, {"url": "https://www.consob.it/documents/11973/11173223/opa_eles_cs20260317.pdf/08ed15b7-c1de-5893-c343-9d5286ae7d92?version=1.0&t=1774264157554&download=false", "label": "Comunicato sui risultati definitivi a seguito della riapertura dei termini"}]}	2026-05-19 14:42:07.43528+00
336	337	2026-05-19 14:42:08.872015+00	filing_consob	Consob documento d'offerta — offerente: BackSpin Spa, visée: Spindox Spa (ref CONSOB-opa_spindox_20251215)	https://www.consob.it/documents/11973/9797550/opa_spindox_20251215.pdf/05e590ab-3b41-70e4-dd5a-3993e348c7f1?version=1.0&t=1765794867359&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_obligatoire", "consob_ref": "CONSOB-opa_spindox_20251215", "period_end": "2026-01-16", "description": "Offerta pubblica di acquisto volontaria totalitaria promossa da BackSpin Spa , obbligatoria ai sensi dell'articolo 12 dello Statuto di Spindox, su un massimo di 1.144.146 azioni ordinarie emesse da Spindox Spa , rappresentative del 19,07% del capitale sociale dell'Emittente. Il corrispettivo unitario è pari a 13,00 euro per ciascuna azione cum dividendo .", "page_number": 1, "target_name": "Spindox Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "13.00", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "AVENTE A OGGETTO AZIONI ORDINARIE DI", "offerente_name_from_pdf": "BackSpin S.p.A"}, "period_start": "2025-12-15", "offerente_name": "BackSpin Spa", "additional_links": [{"url": "https://www.consob.it/documents/11973/9797550/opa_spindox_20260105.pdf/8585c66c-a5f9-7c68-1c00-08ef45cf1a37?version=1.0&t=1768222028853&download=false", "label": "Comunicato sul superamento soglia del 95%"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_spindox_cs_20260120.pdf/e01665f2-818f-7f38-bb3f-4c63fc615032?version=1.0&t=1768999319775&download=false", "label": "Comunicato sui risultati definitivi dell'offerta"}]}	2026-05-19 14:42:08.87038+00
337	338	2026-05-19 14:42:09.876458+00	filing_consob	Consob documento d'offerta — offerente: Mare Engineering Group Spa, visée: Eles Semiconductor Equipment Spa (ref CONSOB-opa_mare_20251205)	https://www.consob.it/documents/11973/9797550/opa_mare_20251205.pdf/efe44fae-dbee-db5a-6b36-6dc1d011d52e?version=1.0&t=1764331106900&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_volontaire_totalitaria", "consob_ref": "CONSOB-opa_mare_20251205", "period_end": "2025-12-30", "description": "Offerta pubblica di acquisto volontaria totalitaria promossa da Mare Engineering Group Spa, ai sensi degli articoli 102 e seguenti del Tuf su azioni Eles Semiconductor Equipment Spa . Il corrispettivo unitario è pari a 2,61 euro per ciascuna azione.", "page_number": 1, "target_name": "Eles Semiconductor Equipment Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "2.61", "opening_date": "2025-12-05", "official_visa": null, "closing_date_est": "2025-12-30", "announcement_date": null, "target_name_from_pdf": "Eles Semiconductor Equipment S.p.A", "offerente_name_from_pdf": "Mare Engineering Group S.p.A"}, "period_start": "2025-12-05", "offerente_name": "Mare Engineering Group Spa", "additional_links": [{"url": "https://www.consob.it/documents/11973/9797550/opa_mare_cs20251204.pdf/3275a6c1-e7d5-bd21-147c-f7bd35f35d6c?version=1.0&t=1765456243400&download=false", "label": "Comunicato dell'emittente"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_marecs20251210.pdf/e377dce9-83d4-3ccc-0880-b031ca29aca7?version=1.0&t=1765447286753&download=false", "label": "Comunicato sull'incremento del corrispettivo dell'offerta"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_mare_cs20251219.pdf/bb576d9c-a2e6-b6d7-cfc9-ab061d466c16?version=1.0&t=1766423912657&download=false", "label": "Integrazione del Comunicato dell'Emittente"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_mare_cs20251229.pdf/40d32f58-92b8-cb16-ea5d-4f82125b0a09?version=1.0&t=1767175861400&download=false", "label": "Comunicato sulla scadenza dell'offerta"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_eles_cs_20251230.pdf/51a46e39-b58f-67f5-0cff-d20b6da97ce4?version=1.0&t=1767869249935&download=false", "label": "Comunicato sui risultati provvisori dell’offerta"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_eles_cs_20260105.pdf/da4d8e91-0758-861b-3efb-40a8877590e5?version=1.0&t=1767869472802&download=false", "label": "Comunicato sulla revoca delle adesioni"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_mare_cs20260109.pdf/88517ac3-4cfc-e05e-4008-749a7c7d0ce9?version=1.0&t=1768200878575&download=false", "label": "Comunicato sui risultati definitivi dell'offerta"}, {"url": "https://www.consob.it/documents/11973/11173223/opa_mare_cs20260210.pdf/8a452cc5-5885-66eb-dfa4-42d69ed2846c?version=1.0&t=1771330317999&download=false", "label": "Comunicato sul conguaglio"}]}	2026-05-19 14:42:09.874764+00
338	339	2026-05-19 14:42:12.710125+00	filing_consob	Consob documento d'offerta — offerente: Wing BidCo Spa, visée: Ala Spa (ref CONSOB-opa_ala_20251201)	https://www.consob.it/documents/11973/9797550/opa_ala_20251201.pdf/2a6a3d66-37c0-f56c-ac6b-41cadd8ab468?version=1.0&t=1765359905870&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_obligatoire", "consob_ref": "CONSOB-opa_ala_20251201", "period_end": "2025-12-19", "description": "Offerta pubblica di acquisto obbligatoria totalitaria, promossa ai sensi degli artt. 102 e seguenti del d. lgs. n. 58 del 1998, da Wing BidCo Spa , su 912.030 azioni Ala Spa , rappresentative del 10,10% del capitale sociale dell’Emittente. Il corrispettivo è pari a Euro 36,08 per ciascuna azione.", "page_number": 1, "target_name": "Ala Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "36.08", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "A.L.A. S.p.A", "offerente_name_from_pdf": "Wing BidCo S.p.A"}, "period_start": "2025-12-01", "offerente_name": "Wing BidCo Spa", "additional_links": [{"url": "https://www.consob.it/documents/11973/9797550/opa_ala_cs20251205.pdf/190fc8c6-5901-fb7d-935f-d9d6428fcb70?version=1.0&t=1766133466426&download=false", "label": "Comunicato sul superamento del 90% soglia"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_ala_20251222.pdf/fca18a1a-cc7e-88bf-3400-9d99f581c343?version=1.0&t=1766485244114&download=false", "label": "Comunicato sui risultati definitivi dell'offerta"}]}	2026-05-19 14:42:12.707756+00
339	340	2026-05-19 14:42:14.117361+00	filing_consob	Consob documento d'offerta — offerente: Almaviva Spa, visée: Almawave Spa (ref CONSOB-opa_almawave_20251117)	https://www.consob.it/documents/11973/9797550/opa_almawave_20251117.pdf/aee6d015-accb-eac7-2e08-481fec834ea2?version=1.0&t=1763130632619&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_volontaire_totalitaria", "consob_ref": "CONSOB-opa_almawave_20251117", "period_end": "2025-12-05", "description": "Documento concernente l’offerta pubblica di acquisto volontaria promossa da Almaviva Spa su un massimo di 6.312.522 azioni ordinarie emesse da Almawave Spa , rappresentative del 21,05% del capitale sociale dell’Emittente, corrispondenti alla totalità delle azioni in circolazione, dedotte le 23.670.022 azioni, pari al 78,95% del capitale sociale dell’Emittente, detenute dall’Offerente, ad un prezzo per azione pari a 4,30 euro cum dividendo.", "page_number": 1, "target_name": "Almawave Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "4.30", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "per ciascuna azione ordinaria", "offerente_name_from_pdf": "ALMAVIVA S.p.A"}, "period_start": "2025-11-17", "offerente_name": "Almaviva Spa", "additional_links": [{"url": "https://www.consob.it/documents/11973/9797550/opa_almawave_cs20251210.pdf/be4df9e8-2e39-021b-9b7f-23252d0b8500?version=1.0&t=1765456648795&download=false", "label": "Comuniato sui risultati definitivi dell'offerta"}]}	2026-05-19 14:42:14.114292+00
340	341	2026-05-19 14:42:16.03903+00	filing_consob	Consob documento d'offerta — offerente: Icop Spa Società Benefit, visée: Palingeo (ref CONSOB-opa_palingeo_20251027)	https://www.consob.it/documents/11973/9797550/opa_palingeo_20251027.pdf/cf025b6c-b585-7cf4-3224-6ed2fc9fc433?version=1.0&t=1761559308256&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_obligatoire", "consob_ref": "CONSOB-opa_palingeo_20251027", "period_end": "2025-11-14", "description": "Offerta pubblica di acquisto totalitaria obbligatoria promossa, ai sensi degli articoli 102 e ss. del d.lgs. n. 58 del 1998, da Icop Spa Società Benefit su un massimo di 2.706.060 azioni ordinarie di Palingeo , pari alla totalità delle azioni in circolazione, dedotte le 4.275.000 azioni detenute da Icop. Il corrispettivo è pari a Euro 6,00 per ciascuna azione.", "page_number": 1, "target_name": "Palingeo", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "6.00", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "avente a oggetto le azioni ordinarie della società", "offerente_name_from_pdf": "I.CO.P. S.p.A. Società Benefit"}, "period_start": "2025-10-27", "offerente_name": "Icop Spa Società Benefit", "additional_links": [{"url": "https://www.consob.it/documents/11973/9797550/opa_palingeo_cs20251112.pdf/0c9dd3d5-ccb4-4118-36e0-3d85b9f58e39?version=1.0&t=1763025746546&download=false", "label": "Comunicato sulla proroga del periodo di adesione"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_palingeo_cs20251206.pdf/ddfc51c9-9eb0-fd99-9e0d-433579c74829?version=1.0&t=1765794865260&download=false", "label": "Comunicato sull'incremento del corrispettivo"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_palingeo_cs20251212.pdf/587ece1c-49ef-fbf8-5b7a-d19be46aa36e?version=1.0&t=1765794866313&download=false", "label": "Comunicato sulla proroga del periodo di adesione"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_palingeo_cs20251222.pdf/7fb495fa-e587-4709-1254-f96a09dd4efa?version=1.0&t=1766498815187&download=false", "label": "Comunicato sui risultati definitivi dell'offerta"}]}	2026-05-19 14:42:16.037318+00
353	354	2026-05-19 16:22:37.866187+00	filing_bafin	BaFin Angebotsunterlage — Bieter: Apeiron Investment Group Ltd, Zielgesellschaft: Heidelberger Beteiligungsholding AG (ref BAFIN-DE000A254294-20250804)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/heidel.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE000A254294-20250804", "deal_type": "opa_obligatoire", "bieter_name": "Apeiron Investment Group Ltd", "target_isin": "DE000A254294", "target_name": "Heidelberger Beteiligungsholding AG", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/heidel.html?nn=151388", "has_document": true, "is_amendment": false, "opening_date": "2024-01-01", "pdf_metadata": {"currency": "EUR", "offer_price": "99.15", "opening_date": "2024-01-01", "closing_date_est": "2024-12-31", "offer_type_from_pdf": "Pflichtangebot", "bieter_name_from_pdf": "gehaltenen, auf den Inhaber", "target_name_from_pdf": "gemeinsam handelnde Personen .................................... 32"}, "offer_type_raw": "Pflichtangebot", "veroeffentlichung_date": "2025-08-04"}	2026-05-19 16:22:37.863174+00
341	342	2026-05-19 14:42:17.268309+00	filing_consob	Consob documento d'offerta — offerente: Banca Monte dei Paschi di Siena Spa, visée: Mediobanca-Banca di Credito Finanziario Spa (ref CONSOB-ops_montepaschi_20250714)	https://www.consob.it/documents/11973/9797550/ops_montepaschi_20250714.pdf/3c5564d1-e993-8042-0f67-aa8ca1264b0e?version=1.0&t=1751693617850&download=false	{"source": "consob_documenti_opa", "deal_type": "opas", "consob_ref": "CONSOB-ops_montepaschi_20250714", "period_end": "2025-09-08", "description": "Offerta pubblica di scambio totalitaria volontaria promossa da Banca Monte dei Paschi di Siena Spa sulle azioni ordinarie di Mediobanca-Banca di Credito Finanziario Spa. Corrispettivo unitario offerto n. 2,533 azioni ordinarie di Banca Monte dei Paschi di Siena S.p.A. di nuova emissione per ciascuna azione ordinaria di Mediobanca – Banca di Credito Finanziario Società per Azioni portata in adesione all'Offerta", "page_number": 1, "target_name": "Mediobanca-Banca di Credito Finanziario Spa", "has_document": true, "pdf_metadata": {"currency": null, "offer_price": null, "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "OFFERENTE", "offerente_name_from_pdf": "Strumenti finanziari oggetto dell"}, "period_start": "2025-07-14", "offerente_name": "Banca Monte dei Paschi di Siena Spa", "additional_links": [{"url": "https://www.consob.it/documents/11973/9797550/ops_montepaschi_cs_20250911.pdf/18c0fc9d-c6d2-b015-3ef6-aad97909aa6d?version=1.0&t=1759313241040&download=false", "label": "Comunicato sui risultati definiti dell'offerta"}, {"url": "https://www.consob.it/documents/11973/9797550/ops_montepaschi_cs_20250925.pdf/8708c654-1114-95f7-5246-0f2d470367e0?version=1.0&t=1759313242284&download=false", "label": "Comunicato sui risultati definitivi della riapertura dei termini"}]}	2026-05-19 14:42:17.266828+00
342	343	2026-05-19 14:42:18.788322+00	filing_consob	Consob documento d'offerta — offerente: Octagon BidCo Spa, visée: Bialetti Spa (ref CONSOB-opa_bialetti_20250707)	https://www.consob.it/documents/11973/9797550/opa_bialetti_20250707.pdf/ec0fe530-d442-b144-3bf2-7a86415326a7?version=1.0&t=1752150728895&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_obligatoire", "consob_ref": "CONSOB-opa_bialetti_20250707", "period_end": "2025-07-25", "description": "Offerta pubblica di acquisto obbligatoria totalitaria promossa da Octagon BidCo Spa , ai sensi degli articoli 102 e 106, comma 1, del Tuf, su azioni Bialetti Spa . Il corrispettivo è pari a Euro 0,467 cum dividendo per ciascuna azione.", "page_number": 1, "target_name": "Bialetti Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "0.467", "opening_date": "2025-07-07", "official_visa": null, "closing_date_est": "2025-07-25", "announcement_date": null, "target_name_from_pdf": "O AVENTI COME SOTTOSTANTE DETTI STRUMENTI", "offerente_name_from_pdf": "Octagon BidCo S.p.A"}, "period_start": "2025-07-07", "offerente_name": "Octagon BidCo Spa", "additional_links": [{"url": "https://www.consob.it/documents/11973/9797550/opa_bialetti_20250707_cs_20250728.pdf/759ac40a-a926-6154-af02-95a8e3052c96?version=1.0&t=1757928848468&download=false", "label": "Comunicato sui risultati definitivi dell'offerta"}]}	2026-05-19 14:42:18.786588+00
343	344	2026-05-19 14:42:19.783622+00	filing_consob	Consob documento d'offerta — offerente: ?, visée: Banca Popolare di Sondrio S (ref CONSOB-ops_Banca_Popolare_Sondrio_20250616)	https://www.consob.it/documents/11973/9797550/ops_Banca_Popolare_Sondrio_20250616.pdf/f554472c-33fe-1ede-ad0e-63d53f5ff8fa?version=1.0&t=1749203433633&download=false	{"source": "consob_documenti_opa", "deal_type": "opas", "consob_ref": "CONSOB-ops_Banca_Popolare_Sondrio_20250616", "period_end": "2025-07-11", "description": "Offerta pubblica di scambio volontaria totalitaria promossa, ai sensi degli articoli 102 e 106, comma 4, del D. Lgs. n. 58 del 1998, da BPER Banca S .p.A. su azioni ordinarie emesse da Banca Popolare di Sondrio S .p.A .. Il corrispettivo riconosciuto dall’offerente a ciascun aderente all’offerta di scambio è rappresentato da 1,450 azioni ordinarie BPER Banca S.p.A. di nuova emissione per ogni azione Banca Popolare di Sondrio S.p.A ..", "page_number": 1, "target_name": "Banca Popolare di Sondrio S", "has_document": true, "pdf_metadata": {"currency": null, "offer_price": null, "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "Banca Popolare di Sondrio S.p.A", "offerente_name_from_pdf": "BPER Banca S.p.A"}, "period_start": "2025-06-16", "offerente_name": null, "additional_links": [{"url": "https://www.consob.it/documents/11973/9797550/ops_csbancapopsondrio.pdf/b85bb8a1-7660-b484-fa7b-0662af8b9a25?version=1.0&t=1749819904472&download=false", "label": "Comunicato dell'Emittente"}, {"url": "https://www.consob.it/documents/11973/9797550/ops_bancopopsondrio_20250703.pdf/b9a09d9d-f64d-86f8-0e35-277157256a95?version=1.0&t=1751620831231&download=false", "label": "Comunicato sull'aumento del corrispettivo dell'ops"}, {"url": "https://www.consob.it/documents/11973/9797550/ops_bps_cs20250715.pdf/43c8c0f1-16b4-b859-6cca-b410c8aa2eed?version=1.0&t=1752655568574&download=false", "label": "Comunicato sui risultati definitivi dell'offerta"}, {"url": "https://www.consob.it/documents/11973/9797550/ops_bps_cs20250728.pdf/10308701-cd8c-5ae3-a05e-c1bb1e2858be?version=1.0&t=1753943039875&download=false", "label": "Comunicato sui risultati definitivi della riapertura dei termini"}]}	2026-05-19 14:42:19.782273+00
344	345	2026-05-19 14:42:20.755632+00	filing_consob	Consob documento d'offerta — offerente: ?, visée: Alkemy S (ref CONSOB-opa_Alkemy_20250609)	https://www.consob.it/documents/11973/9797550/opa_Alkemy_20250609.pdf/7d34b102-d152-787c-41ac-e5152d1fadd9?version=1.0&t=1749480240987&download=false	{"source": "consob_documenti_opa", "deal_type": null, "consob_ref": "CONSOB-opa_Alkemy_20250609", "period_end": "2025-07-04", "description": "Documento informativo in merito alla procedura di obbligo di acquisto di cui all'articolo 108, comma 2, del d.lgs. n. 58 del 1998, avente ad oggetto le azioni ordinarie emesse da Alkemy S.p.A. , assolto da Retex S.p.A. - Società Benefit . Il corrispettivo è pari a 12,00 euro per azione.", "page_number": 1, "target_name": "Alkemy S", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "12.00", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "GLI STRUMENTI FINANZIARI OGGETTO DELLA PROCEDURA .............. 46", "offerente_name_from_pdf": null}, "period_start": "2025-06-09", "offerente_name": null, "additional_links": [{"url": "https://www.consob.it/documents/11973/9797550/opa_alkemy_cs20250707.pdf/f00631d0-a13b-6828-232c-120ee9fb9b6e?version=1.0&t=1752745296289&download=false", "label": "Comunicato sui risultati definitivi della procedura"}]}	2026-05-19 14:42:20.753545+00
345	346	2026-05-19 14:42:21.748947+00	filing_consob	Consob documento d'offerta — offerente: Zenit Spa, visée: Il Sole 24 Ore Spa (ref CONSOB-Opa_IlSole24Ore_20250603)	https://www.consob.it/documents/11973/9797550/Opa_IlSole24Ore_20250603.pdf/9f1eaf2d-4eb3-3612-aab0-b7eb2eb29598?version=1.0&t=1748421998484&download=false	{"source": "consob_documenti_opa", "deal_type": "opa_volontaire_totalitaria", "consob_ref": "CONSOB-Opa_IlSole24Ore_20250603", "period_end": "2025-06-30", "description": "Offerta pubblica di acquisto volontaria totalitaria promossa, ai sensi dell’art. 102 del d. lgs. n. 58 del 1998, da Zenit Spa su un massimo di 18.020.513 azioni speciali emesse da Il Sole 24 Ore Spa . Il corrispettivo è pari a 1,100 euro per ciascuna azione speciale portata in adesione all'offerta.", "page_number": 1, "target_name": "Il Sole 24 Ore Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "1.100", "opening_date": "2025-06-03", "official_visa": null, "closing_date_est": "2025-06-30", "announcement_date": null, "target_name_from_pdf": "al 31 dicembre 2024 e resoconti", "offerente_name_from_pdf": "Zenit S.p.A"}, "period_start": "2025-06-03", "offerente_name": "Zenit Spa", "additional_links": [{"url": "https://www.consob.it/documents/11973/9797550/opa_ilsole24ore_cs20250702.pdf/c4632734-224e-4d37-bc95-9ccbea35a83c?version=1.0&t=1752744919495&download=false", "label": "Comunicato sui risultati definitivi dell'offerta"}]}	2026-05-19 14:42:21.747038+00
346	347	2026-05-19 14:42:22.995307+00	filing_consob	Consob documento d'offerta — offerente: Banca Ifis Spa, visée: Illimity Bank Spa (ref CONSOB-opa_illimity_20250519)	https://www.consob.it/documents/11973/9797550/opa_illimity_20250519.pdf/4c9b537c-54b0-0057-357a-451785b2511d?version=1.0&t=1747032853909&download=false	{"source": "consob_documenti_opa", "deal_type": "opas", "consob_ref": "CONSOB-opa_illimity_20250519", "period_end": "2025-06-27", "description": "Offerta pubblica di acquisto e scambio (OPAS) volontaria promossa da Banca Ifis Spa su complessive 84.067.808 azioni ordinarie emesse da Illimity Bank Spa . Per ciascuna azione portata in adesione all’offerta sarà riconosciuto un corrispettivo complessivo unitario composto da: ( i ) n. 0,10 azioni Banca Ifis di nuova emissione; e da ( ii ) Euro 1,414 (fatti salvi gli aggiustamenti indicati nel documento d’offerta).", "page_number": 1, "target_name": "Illimity Bank Spa", "has_document": true, "pdf_metadata": {"currency": "EUR", "offer_price": "1.414", "opening_date": null, "official_visa": null, "closing_date_est": null, "announcement_date": null, "target_name_from_pdf": "illimity Bank S.p.A", "offerente_name_from_pdf": "BANCA IFIS S.p.A"}, "period_start": "2025-05-19", "offerente_name": "Banca Ifis Spa", "additional_links": [{"url": "https://www.consob.it/documents/11973/9797550/opa_illimity_comunicato_20250516.pdf/f108318f-f6ab-c7d2-b695-cac322443423?version=1.0&t=1747663372106&download=false", "label": "Comunicato del Consiglio di Amministrazione"}, {"url": "https://www.consob.it/documents/11973/9797550/opa_illimity_cs20250701.pdf/6c977d22-8a86-5260-2dbe-c47098d42cd0?version=1.0&t=1758873800782&download=false", "label": "Comunicato sui risultati definitivi dell'offerta"}]}	2026-05-19 14:42:22.993737+00
347	348	2026-05-19 16:22:31.029438+00	filing_bafin	BaFin Angebotsunterlage — Bieter: UniCredit S.p.A, Zielgesellschaft: COMMERZBANK Aktiengesellschaft (ref BAFIN-DE000CBK1001-20260505)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/commerzbank.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE000CBK1001-20260505", "deal_type": "opa_volontaire_totalitaria", "bieter_name": "UniCredit S.p.A", "target_isin": "DE000CBK1001", "target_name": "COMMERZBANK Aktiengesellschaft", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/commerzbank.html?nn=151388", "has_document": true, "is_amendment": false, "pdf_metadata": {"currency": "EUR", "offer_price": "1.00", "opening_date": null, "closing_date_est": null, "offer_type_from_pdf": "ÜBERNAHMEANGEBOT", "bieter_name_from_pdf": "IN, IHRER BETEILIGUNGSVERHÄLTNISSE UND", "target_name_from_pdf": null}, "offer_type_raw": "Übernahmeangebot", "veroeffentlichung_date": "2026-05-05"}	2026-05-19 16:22:30.99317+00
348	349	2026-05-19 16:22:31.7146+00	filing_bafin	BaFin Angebotsunterlage — Bieter: Worthington Steel GmbH, Zielgesellschaft: Klöckner & Co SE (ref BAFIN-DE000KC01000-20260205)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/kloeckner-co-se-2.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE000KC01000-20260205", "deal_type": "opa_volontaire_totalitaria", "bieter_name": "Worthington Steel GmbH", "target_isin": "DE000KC01000", "target_name": "Klöckner & Co SE", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/kloeckner-co-se-2.html?nn=151388", "has_document": true, "is_amendment": false, "pdf_metadata": {"currency": "EUR", "offer_price": "11.00", "opening_date": null, "closing_date_est": null, "offer_type_from_pdf": "ÜBERNAHMEANGEBOT", "bieter_name_from_pdf": "UND IHRER", "target_name_from_pdf": null}, "offer_type_raw": "Übernahmeangebot", "veroeffentlichung_date": "2026-02-05"}	2026-05-19 16:22:31.711996+00
349	350	2026-05-19 16:22:32.892314+00	filing_bafin	BaFin Angebotsunterlage — Bieter: Zest Bidco GmbH, Zielgesellschaft: PSI Software SE (ref BAFIN-DE000A0Z1JH9-20251117)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/PSI_Software.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE000A0Z1JH9-20251117", "deal_type": "opa_volontaire_totalitaria", "bieter_name": "Zest Bidco GmbH", "target_isin": "DE000A0Z1JH9", "target_name": "PSI Software SE", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/PSI_Software.html?nn=151388", "has_document": true, "is_amendment": false, "pdf_metadata": {"currency": "EUR", "offer_price": "45.00", "opening_date": null, "closing_date_est": null, "offer_type_from_pdf": "ÜBERNAHMEANGEBOT", "bieter_name_from_pdf": "UND IHRER", "target_name_from_pdf": null}, "offer_type_raw": "Übernahmeangebot", "veroeffentlichung_date": "2025-11-17"}	2026-05-19 16:22:32.887981+00
350	351	2026-05-19 16:22:33.701502+00	filing_bafin	BaFin Angebotsunterlage — Bieter: S77 Holdings GmbH, Zielgesellschaft: Turbon AG (ref BAFIN-DE0007504508-20251021)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/turbon.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE0007504508-20251021", "deal_type": "opa_obligatoire", "bieter_name": "S77 Holdings GmbH", "target_isin": "DE0007504508", "target_name": "Turbon AG", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/turbon.html?nn=151388", "has_document": true, "is_amendment": false, "pdf_metadata": {"currency": "EUR", "offer_price": "3.34", "opening_date": null, "closing_date_est": null, "offer_type_from_pdf": "PFLICHTANGEBOT", "bieter_name_from_pdf": "in ........................................ 9", "target_name_from_pdf": "veröffentlicht. Ebenso hat Herr Hol-"}, "offer_type_raw": "Pflichtangebot", "veroeffentlichung_date": "2025-10-21"}	2026-05-19 16:22:33.698063+00
351	352	2026-05-19 16:22:34.92607+00	filing_bafin	BaFin Angebotsunterlage — Bieter: Obotritia Capital KGaA, Zielgesellschaft: Readcrest Capital AG (ref BAFIN-DE000A1E89S5-20251002)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/readcrest_capital.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE000A1E89S5-20251002", "deal_type": "opa_volontaire_totalitaria", "bieter_name": "Obotritia Capital KGaA", "target_isin": "DE000A1E89S5", "target_name": "Readcrest Capital AG", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/readcrest_capital.html?nn=151388", "has_document": true, "is_amendment": false, "opening_date": "2024-01-01", "pdf_metadata": {"currency": "EUR", "offer_price": "1.30", "opening_date": "2024-01-01", "closing_date_est": "2024-12-31", "offer_type_from_pdf": "Übernahmeangebot", "bieter_name_from_pdf": "gehaltenen, auf den Inhaber", "target_name_from_pdf": "gemeinsam handelnde Personen .................................... 35"}, "offer_type_raw": "Übernahmeangebot", "veroeffentlichung_date": "2025-10-02"}	2026-05-19 16:22:34.922166+00
352	353	2026-05-19 16:22:36.016313+00	filing_bafin	BaFin Angebotsunterlage — Bieter: JINGDONG HOLDING GERMANY GMBH, Zielgesellschaft: CECONOMY AG (ref BAFIN-DE0007257503-20250901)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/CECONOMY.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE0007257503-20250901", "deal_type": "opa_volontaire_totalitaria", "bieter_name": "JINGDONG HOLDING GERMANY GMBH", "target_isin": "DE0007257503", "target_name": "CECONOMY AG", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/CECONOMY.html?nn=151388", "has_document": true, "is_amendment": false, "pdf_metadata": {"currency": "EUR", "offer_price": "4.60", "opening_date": null, "closing_date_est": null, "offer_type_from_pdf": "ÜBERNAHMEANGEBOT", "bieter_name_from_pdf": "gehaltenen auf den Inhaber lautenden Stückaktien", "target_name_from_pdf": null}, "offer_type_raw": "Übernahmeangebot", "veroeffentlichung_date": "2025-09-01"}	2026-05-19 16:22:36.013779+00
354	355	2026-05-19 16:22:38.912089+00	filing_bafin	BaFin Angebotsunterlage — Bieter: SALTARAX GmbH, Zielgesellschaft: Francotyp-Postalia Holding AG (ref BAFIN-DE000FPH9000-20250731)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Francotyp_Saltarax.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE000FPH9000-20250731", "deal_type": "opa_volontaire_parziale", "bieter_name": "SALTARAX GmbH", "target_isin": "DE000FPH9000", "target_name": "Francotyp-Postalia Holding AG", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Francotyp_Saltarax.html?nn=151388", "has_document": true, "is_amendment": false, "opening_date": "2025-07-31", "pdf_metadata": {"currency": "EUR", "offer_price": "2.80", "opening_date": "2025-07-31", "closing_date_est": "2025-08-28", "offer_type_from_pdf": "Erwerbsangebot", "bieter_name_from_pdf": "n .................................... 16", "target_name_from_pdf": "gemeinsam handelnde Personen .................................... 38"}, "offer_type_raw": "Teilerwerbsangebot", "veroeffentlichung_date": "2025-07-31"}	2026-05-19 16:22:38.90937+00
355	356	2026-05-19 16:22:39.678965+00	filing_bafin	BaFin Angebotsunterlage — Bieter: SCGI Corporate Finance GmbH, Zielgesellschaft: Leo International Precision Health Aktiengesellschaft (ref BAFIN-DE0005490601-20250725)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Leo_International.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE0005490601-20250725", "deal_type": "opa_obligatoire", "bieter_name": "SCGI Corporate Finance GmbH", "target_isin": "DE0005490601", "target_name": "Leo International Precision Health Aktiengesellschaft", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Leo_International.html?nn=151388", "has_document": true, "is_amendment": false, "pdf_metadata": {"currency": "EUR", "offer_price": "0.71", "opening_date": null, "closing_date_est": null, "offer_type_from_pdf": "Pflichtangebot", "bieter_name_from_pdf": "n gehaltenen", "target_name_from_pdf": "handelnde Personen ..................................................... 14"}, "offer_type_raw": "Pflichtangebot", "veroeffentlichung_date": "2025-07-25"}	2026-05-19 16:22:39.676196+00
356	357	2026-05-19 16:22:40.633223+00	filing_bafin	BaFin Angebotsunterlage — Bieter: FUTRUE GmbH, Zielgesellschaft: PharmaSGP Holding SE (ref BAFIN-DE000A2P4LJ5-20250714)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/PharmaSGP.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE000A2P4LJ5-20250714", "deal_type": "delisting_offer", "bieter_name": "FUTRUE GmbH", "target_isin": "DE000A2P4LJ5", "target_name": "PharmaSGP Holding SE", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/PharmaSGP.html?nn=151388", "has_document": true, "is_amendment": false, "pdf_metadata": {"currency": "EUR", "offer_price": "28.00", "opening_date": null, "closing_date_est": null, "offer_type_from_pdf": "DELISTING-ERWERBSANGEBOT", "bieter_name_from_pdf": "UND IHRER", "target_name_from_pdf": null}, "offer_type_raw": "Delisting-Erwerbsangebot", "veroeffentlichung_date": "2025-07-14"}	2026-05-19 16:22:40.630612+00
357	358	2026-05-19 16:22:41.660041+00	filing_bafin	BaFin Angebotsunterlage — Bieter: Francotyp-Postalia Holding AG, Zielgesellschaft: Francotyp-Postalia Holding AG (ref BAFIN-DE000FPH9000-20250709)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Francotyp.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE000FPH9000-20250709", "deal_type": "delisting_offer", "bieter_name": "Francotyp-Postalia Holding AG", "target_isin": "DE000FPH9000", "target_name": "Francotyp-Postalia Holding AG", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Francotyp.html?nn=151388", "has_document": true, "is_amendment": false, "opening_date": "2025-07-09", "pdf_metadata": {"currency": "EUR", "offer_price": "2.27", "opening_date": "2025-07-09", "closing_date_est": "2025-08-07", "offer_type_from_pdf": null, "bieter_name_from_pdf": "in“ oder „FP“), an die Aktionäre der", "target_name_from_pdf": "des Delisting-Angebots"}, "offer_type_raw": "Delisting-Rückerwerbsangebot", "veroeffentlichung_date": "2025-07-09"}	2026-05-19 16:22:41.656531+00
358	359	2026-05-19 16:22:43.026407+00	filing_bafin	BaFin Angebotsunterlage — Bieter: Leonardo Art Holdings GmbH, Zielgesellschaft: artnet AG (ref BAFIN-DE000A1K0375-20250708)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/artnetAG.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE000A1K0375-20250708", "deal_type": "delisting_offer", "bieter_name": "Leonardo Art Holdings GmbH", "target_isin": "DE000A1K0375", "target_name": "artnet AG", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/artnetAG.html?nn=151388", "has_document": true, "is_amendment": false, "pdf_metadata": {"currency": "EUR", "offer_price": "11.25", "opening_date": null, "closing_date_est": null, "offer_type_from_pdf": "PFLICHTANGEBOT", "bieter_name_from_pdf": "UND IHRER", "target_name_from_pdf": null}, "offer_type_raw": "Delisting-Übernahmeangebot", "veroeffentlichung_date": "2025-07-08"}	2026-05-19 16:22:43.022884+00
359	360	2026-05-19 16:22:43.832056+00	filing_bafin	BaFin Angebotsunterlage — Bieter: H&R Holding GmbH, Zielgesellschaft: H&R GmbH & Co. KGaA (ref BAFIN-DE000A2E4T77-20250630)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/H_R2.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE000A2E4T77-20250630", "deal_type": "opa_volontaire_parziale", "bieter_name": "H&R Holding GmbH", "target_isin": "DE000A2E4T77", "target_name": "H&R GmbH & Co. KGaA", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/H_R2.html?nn=151388", "has_document": true, "is_amendment": true, "pdf_metadata": {"currency": "EUR", "offer_price": "5.00", "opening_date": null, "closing_date_est": null, "offer_type_from_pdf": "Erwerbsangebot", "bieter_name_from_pdf": "in), hat am", "target_name_from_pdf": null}, "offer_type_raw": "Erwerbsangebot Änderung", "veroeffentlichung_date": "2025-06-30"}	2026-05-19 16:22:43.828285+00
360	361	2026-05-19 16:22:45.018993+00	filing_bafin	BaFin Angebotsunterlage — Bieter: United Internet AG, Zielgesellschaft: 1&1 AG (ref BAFIN-DE0005545503-20250605)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/United_Internet.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE0005545503-20250605", "deal_type": "opa_volontaire_parziale", "bieter_name": "United Internet AG", "target_isin": "DE0005545503", "target_name": "1&1 AG", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/United_Internet.html?nn=151388", "has_document": true, "is_amendment": false, "pdf_metadata": {"currency": "EUR", "offer_price": "18.50", "opening_date": null, "closing_date_est": null, "offer_type_from_pdf": "Erwerbsangebot", "bieter_name_from_pdf": "in ........................................................................................................ 14", "target_name_from_pdf": "gemeinsam handelnde Personen .......................................... 30"}, "offer_type_raw": "Teilerwerbsangebot", "veroeffentlichung_date": "2025-06-05"}	2026-05-19 16:22:45.016545+00
362	363	2026-05-19 16:22:47.320312+00	filing_bafin	BaFin Angebotsunterlage — Bieter: Caesar BidCo GmbH, Zielgesellschaft: CompuGroup Medical SE & Co . KGaA (ref BAFIN-DE000A288904-20250523)	https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Compu.html?nn=151388	{"source": "bafin_angebotsunterlagen", "bafin_ref": "BAFIN-DE000A288904-20250523", "deal_type": "delisting_offer", "bieter_name": "Caesar BidCo GmbH", "target_isin": "DE000A288904", "target_name": "CompuGroup Medical SE & Co . KGaA", "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Compu.html?nn=151388", "has_document": true, "is_amendment": false, "opening_date": "2024-10-23", "pdf_metadata": {"currency": "EUR", "offer_price": "22.00", "opening_date": "2024-10-23", "closing_date_est": "2024-12-05", "offer_type_from_pdf": "Delisting-Erwerbsangebot", "bieter_name_from_pdf": "gehaltenen auf den Namen lautenden Stückaktien der", "target_name_from_pdf": null}, "offer_type_raw": "Delisting-Erwerbsangebot", "veroeffentlichung_date": "2025-05-23"}	2026-05-19 16:22:47.317421+00
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
-- Data for Name: vendor_api_usage; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.vendor_api_usage (id, vendor, year_month, ts, request_url, target_url, credits_cost, http_status, extra) FROM stdin;
7	scrapingbee	2026-05	2026-05-19 14:41:49.854977+00	https://app.scrapingbee.com/api/v1/	https://www.consob.it/web/area-pubblica/documenti-opa?p_p_id=it_consob_OpaDocumentsPortlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_it_consob_OpaDocumentsPortlet_delta=50&_it_consob_OpaDocumentsPortlet_resetCur=false&_it_consob_OpaDocumentsPortlet_cur=1	1	200	{"render_js": false, "country_code": null, "premium_proxy": false, "spb_resolved_url": "https://www.consob.it/web/area-pubblica/documenti-opa?p_p_id=it_consob_OpaDocumentsPortlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_it_consob_OpaDocumentsPortlet_delta=50&_it_consob_OpaDocumentsPortlet_resetCur=false&_it_consob_OpaDocumentsPortlet_cur=1", "spb_initial_status_code": "200"}
8	scrapingbee	2026-05	2026-05-19 14:42:26.743132+00	https://app.scrapingbee.com/api/v1/	https://www.consob.it/web/area-pubblica/documenti-opa?p_p_id=it_consob_OpaDocumentsPortlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_it_consob_OpaDocumentsPortlet_delta=50&_it_consob_OpaDocumentsPortlet_resetCur=false&_it_consob_OpaDocumentsPortlet_cur=2	1	200	{"render_js": false, "country_code": null, "premium_proxy": false, "spb_resolved_url": "https://www.consob.it/web/area-pubblica/documenti-opa?p_p_id=it_consob_OpaDocumentsPortlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_it_consob_OpaDocumentsPortlet_delta=50&_it_consob_OpaDocumentsPortlet_resetCur=false&_it_consob_OpaDocumentsPortlet_cur=2", "spb_initial_status_code": "200"}
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

SELECT pg_catalog.setval('public.deals_id_seq', 363, true);


--
-- Name: events_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.events_id_seq', 362, true);


--
-- Name: paper_positions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.paper_positions_id_seq', 1, false);


--
-- Name: scores_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.scores_id_seq', 1, false);


--
-- Name: vendor_api_usage_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.vendor_api_usage_id_seq', 8, true);


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
-- Name: vendor_api_usage vendor_api_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_api_usage
    ADD CONSTRAINT vendor_api_usage_pkey PRIMARY KEY (id);


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
-- Name: ix_vendor_api_usage_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vendor_api_usage_ts ON public.vendor_api_usage USING btree (ts);


--
-- Name: ix_vendor_api_usage_vendor_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vendor_api_usage_vendor_month ON public.vendor_api_usage USING btree (vendor, year_month);


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

\unrestrict BJQWjw5zUTSYxU7ggHmBbsSvB9amYfIYk4FkPelcQnDFanEEo20KGDPcN8C91j3

