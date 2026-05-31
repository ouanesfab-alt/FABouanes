--
-- PostgreSQL database dump
--

\restrict s2AtQmzyLT2cmplwLt66oPAni0miz6A5ZCvqP6WqD6J9fed2FgE670Z5eJrY6Vn

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: fabouanes
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO fabouanes;

--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: fabouanes
--

COMMENT ON SCHEMA public IS '';


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: fabouanes
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$;


ALTER FUNCTION public.set_updated_at() OWNER TO fabouanes;

--
-- Name: sync_payment_to_client_history(); Type: FUNCTION; Schema: public; Owner: fabouanes
--

CREATE FUNCTION public.sync_payment_to_client_history() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            v_prev_solde NUMERIC(15,4);
            v_solde NUMERIC(15,4);
            v_montant_achat NUMERIC(15,4);
            v_montant_verse NUMERIC(15,4);
        BEGIN
            IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
                IF NEW.client_id IS NULL THEN
                    IF TG_OP = 'UPDATE' THEN
                        DELETE FROM client_history WHERE payment_id = NEW.id;
                    END IF;
                    RETURN NEW;
                END IF;
            END IF;

            IF TG_OP = 'INSERT' THEN
                SELECT COALESCE(
                    (SELECT solde_cumule FROM client_history WHERE client_id = NEW.client_id ORDER BY operation_date DESC, id DESC LIMIT 1),
                    (SELECT opening_credit FROM clients WHERE id = NEW.client_id),
                    0
                ) INTO v_prev_solde;

                v_montant_achat := CASE WHEN NEW.payment_type='avance' THEN NEW.amount ELSE 0 END;
                v_montant_verse := CASE WHEN NEW.payment_type='versement' THEN NEW.amount ELSE 0 END;
                v_solde := v_prev_solde + v_montant_achat - v_montant_verse;

                INSERT INTO client_history (
                    client_id, operation_date, designation,
                    montant_achat, montant_verse, solde_cumule,
                    ordre_import, source, payment_id, created_at
                ) VALUES (
                    NEW.client_id,
                    NEW.payment_date,
                    CASE
                        WHEN NEW.sale_kind = 'raw' THEN 'Versement lié à la vente matière'
                        WHEN NEW.sale_kind = 'finished' THEN 'Versement lié à la vente produit'
                        ELSE COALESCE(NULLIF(NEW.notes,''), CASE WHEN NEW.payment_type='avance' THEN 'Avance client' ELSE 'Versement client' END)
                    END,
                    v_montant_achat,
                    v_montant_verse,
                    v_solde,
                    (SELECT COALESCE(MAX(ordre_import), -1) + 1
                     FROM client_history WHERE client_id = NEW.client_id),
                    'app',
                    NEW.id,
                    NEW.created_at
                );
            ELSIF TG_OP = 'UPDATE' THEN
                UPDATE client_history
                SET operation_date = NEW.payment_date,
                    designation = CASE
                        WHEN NEW.sale_kind = 'raw' THEN 'Versement lié à la vente matière'
                        WHEN NEW.sale_kind = 'finished' THEN 'Versement lié à la vente produit'
                        ELSE COALESCE(NULLIF(NEW.notes,''), CASE WHEN NEW.payment_type='avance' THEN 'Avance client' ELSE 'Versement client' END)
                    END,
                    montant_achat = CASE WHEN NEW.payment_type='avance' THEN NEW.amount ELSE 0 END,
                    montant_verse = CASE WHEN NEW.payment_type='versement' THEN NEW.amount ELSE 0 END,
                    client_id = NEW.client_id
                WHERE payment_id = NEW.id;
            ELSIF TG_OP = 'DELETE' THEN
                DELETE FROM client_history WHERE payment_id = OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$;


ALTER FUNCTION public.sync_payment_to_client_history() OWNER TO fabouanes;

--
-- Name: sync_raw_sale_to_client_history(); Type: FUNCTION; Schema: public; Owner: fabouanes
--

CREATE FUNCTION public.sync_raw_sale_to_client_history() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            v_prev_solde NUMERIC(15,4);
            v_solde NUMERIC(15,4);
        BEGIN
            IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
                IF NEW.client_id IS NULL THEN
                    IF TG_OP = 'UPDATE' THEN
                        DELETE FROM client_history WHERE raw_sale_id = NEW.id;
                    END IF;
                    RETURN NEW;
                END IF;
            END IF;

            IF TG_OP = 'INSERT' THEN
                SELECT COALESCE(
                    (SELECT solde_cumule FROM client_history WHERE client_id = NEW.client_id ORDER BY operation_date DESC, id DESC LIMIT 1),
                    (SELECT opening_credit FROM clients WHERE id = NEW.client_id),
                    0
                ) INTO v_prev_solde;

                v_solde := v_prev_solde + NEW.total - NEW.amount_paid;

                INSERT INTO client_history (
                    client_id, operation_date, designation,
                    montant_achat, montant_verse, solde_cumule,
                    ordre_import, source, raw_sale_id, created_at
                ) VALUES (
                    NEW.client_id,
                    NEW.sale_date,
                    (SELECT COALESCE(NULLIF(NEW.custom_item_name, ''), r.name) || ' (matière première) - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM raw_materials r WHERE r.id = NEW.raw_material_id),
                    NEW.total,
                    NEW.amount_paid,
                    v_solde,
                    (SELECT COALESCE(MAX(ordre_import), -1) + 1
                     FROM client_history WHERE client_id = NEW.client_id),
                    'app',
                    NEW.id,
                    NEW.created_at
                );
            ELSIF TG_OP = 'UPDATE' THEN
                IF EXISTS(SELECT 1 FROM client_history WHERE raw_sale_id = NEW.id) THEN
                    UPDATE client_history
                    SET operation_date = NEW.sale_date,
                        designation = (SELECT COALESCE(NULLIF(NEW.custom_item_name, ''), r.name) || ' (matière première) - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM raw_materials r WHERE r.id = NEW.raw_material_id),
                        montant_achat = NEW.total,
                        montant_verse = NEW.amount_paid,
                        client_id = NEW.client_id
                    WHERE raw_sale_id = NEW.id;
                ELSE
                    SELECT COALESCE(
                        (SELECT solde_cumule FROM client_history WHERE client_id = NEW.client_id ORDER BY operation_date DESC, id DESC LIMIT 1),
                        (SELECT opening_credit FROM clients WHERE id = NEW.client_id),
                        0
                    ) INTO v_prev_solde;

                    v_solde := v_prev_solde + NEW.total - NEW.amount_paid;

                    INSERT INTO client_history (
                        client_id, operation_date, designation,
                        montant_achat, montant_verse, solde_cumule,
                        ordre_import, source, raw_sale_id, created_at
                    ) VALUES (
                        NEW.client_id,
                        NEW.sale_date,
                        (SELECT COALESCE(NULLIF(NEW.custom_item_name, ''), r.name) || ' (matière première) - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM raw_materials r WHERE r.id = NEW.raw_material_id),
                        NEW.total,
                        NEW.amount_paid,
                        v_solde,
                        (SELECT COALESCE(MAX(ordre_import), -1) + 1
                         FROM client_history WHERE client_id = NEW.client_id),
                        'app',
                        NEW.id,
                        NEW.created_at
                    );
                END IF;
            ELSIF TG_OP = 'DELETE' THEN
                DELETE FROM client_history WHERE raw_sale_id = OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$;


ALTER FUNCTION public.sync_raw_sale_to_client_history() OWNER TO fabouanes;

--
-- Name: sync_sale_to_client_history(); Type: FUNCTION; Schema: public; Owner: fabouanes
--

CREATE FUNCTION public.sync_sale_to_client_history() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            v_prev_solde NUMERIC(15,4);
            v_solde NUMERIC(15,4);
        BEGIN
            IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
                IF NEW.client_id IS NULL THEN
                    IF TG_OP = 'UPDATE' THEN
                        DELETE FROM client_history WHERE sale_id = NEW.id;
                    END IF;
                    RETURN NEW;
                END IF;
            END IF;

            IF TG_OP = 'INSERT' THEN
                SELECT COALESCE(
                    (SELECT solde_cumule FROM client_history WHERE client_id = NEW.client_id ORDER BY operation_date DESC, id DESC LIMIT 1),
                    (SELECT opening_credit FROM clients WHERE id = NEW.client_id),
                    0
                ) INTO v_prev_solde;

                v_solde := v_prev_solde + NEW.total - NEW.amount_paid;

                INSERT INTO client_history (
                    client_id, operation_date, designation,
                    montant_achat, montant_verse, solde_cumule,
                    ordre_import, source, sale_id, created_at
                ) VALUES (
                    NEW.client_id,
                    NEW.sale_date,
                    (SELECT fp.name || ' - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM finished_products fp WHERE fp.id = NEW.finished_product_id),
                    NEW.total,
                    NEW.amount_paid,
                    v_solde,
                    (SELECT COALESCE(MAX(ordre_import), -1) + 1
                     FROM client_history WHERE client_id = NEW.client_id),
                    'app',
                    NEW.id,
                    NEW.created_at
                );
            ELSIF TG_OP = 'UPDATE' THEN
                IF EXISTS(SELECT 1 FROM client_history WHERE sale_id = NEW.id) THEN
                    UPDATE client_history
                    SET operation_date = NEW.sale_date,
                        designation = (SELECT fp.name || ' - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM finished_products fp WHERE fp.id = NEW.finished_product_id),
                        montant_achat = NEW.total,
                        montant_verse = NEW.amount_paid,
                        client_id = NEW.client_id
                    WHERE sale_id = NEW.id;
                ELSE
                    SELECT COALESCE(
                        (SELECT solde_cumule FROM client_history WHERE client_id = NEW.client_id ORDER BY operation_date DESC, id DESC LIMIT 1),
                        (SELECT opening_credit FROM clients WHERE id = NEW.client_id),
                        0
                    ) INTO v_prev_solde;

                    v_solde := v_prev_solde + NEW.total - NEW.amount_paid;

                    INSERT INTO client_history (
                        client_id, operation_date, designation,
                        montant_achat, montant_verse, solde_cumule,
                        ordre_import, source, sale_id, created_at
                    ) VALUES (
                        NEW.client_id,
                        NEW.sale_date,
                        (SELECT fp.name || ' - ' || NEW.quantity || ' ' || COALESCE(NEW.unit, '') FROM finished_products fp WHERE fp.id = NEW.finished_product_id),
                        NEW.total,
                        NEW.amount_paid,
                        v_solde,
                        (SELECT COALESCE(MAX(ordre_import), -1) + 1
                         FROM client_history WHERE client_id = NEW.client_id),
                        'app',
                        NEW.id,
                        NEW.created_at
                    );
                END IF;
            ELSIF TG_OP = 'DELETE' THEN
                DELETE FROM client_history WHERE sale_id = OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$;


ALTER FUNCTION public.sync_sale_to_client_history() OWNER TO fabouanes;

--
-- Name: update_clients_search_vector(); Type: FUNCTION; Schema: public; Owner: fabouanes
--

CREATE FUNCTION public.update_clients_search_vector() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.search_vector := to_tsvector('french',
    COALESCE(NEW.name,'') || ' ' || COALESCE(NEW.phone,'') || ' ' || COALESCE(NEW.address,''));
  RETURN NEW;
END $$;


ALTER FUNCTION public.update_clients_search_vector() OWNER TO fabouanes;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: activity_logs; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.activity_logs (
    id bigint NOT NULL,
    username text NOT NULL,
    action text NOT NULL,
    entity_type text,
    entity_id bigint,
    details text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id integer,
    old_value text,
    new_value text,
    ip_address text
);


ALTER TABLE public.activity_logs OWNER TO fabouanes;

--
-- Name: activity_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.activity_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.activity_logs_id_seq OWNER TO fabouanes;

--
-- Name: activity_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.activity_logs_id_seq OWNED BY public.activity_logs.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO fabouanes;

--
-- Name: api_refresh_tokens; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.api_refresh_tokens (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    token_hash text NOT NULL,
    token_hint text,
    created_ip text,
    user_agent text,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    last_used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.api_refresh_tokens OWNER TO fabouanes;

--
-- Name: api_refresh_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.api_refresh_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.api_refresh_tokens_id_seq OWNER TO fabouanes;

--
-- Name: api_refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.api_refresh_tokens_id_seq OWNED BY public.api_refresh_tokens.id;


--
-- Name: app_settings; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.app_settings (
    key text NOT NULL,
    value text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.app_settings OWNER TO fabouanes;

--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.audit_logs (
    id bigint NOT NULL,
    actor_user_id bigint,
    actor_username text NOT NULL,
    actor_role text NOT NULL,
    source text DEFAULT 'web'::text NOT NULL,
    action text NOT NULL,
    entity_type text,
    entity_id text,
    status text DEFAULT 'success'::text NOT NULL,
    ip_address text,
    user_agent text,
    request_id text,
    before_json text,
    after_json text,
    meta_json text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.audit_logs OWNER TO fabouanes;

--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.audit_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.audit_logs_id_seq OWNER TO fabouanes;

--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;


--
-- Name: backup_jobs; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.backup_jobs (
    id bigint NOT NULL,
    reason text NOT NULL,
    backup_type text DEFAULT 'event'::text NOT NULL,
    local_path text NOT NULL,
    requested_by_user_id bigint,
    status text DEFAULT 'pending'::text NOT NULL,
    context_json text,
    cloud_file_id text,
    cloud_file_name text,
    error_message text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone
);


ALTER TABLE public.backup_jobs OWNER TO fabouanes;

--
-- Name: backup_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.backup_jobs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.backup_jobs_id_seq OWNER TO fabouanes;

--
-- Name: backup_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.backup_jobs_id_seq OWNED BY public.backup_jobs.id;


--
-- Name: backup_runs; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.backup_runs (
    id bigint NOT NULL,
    job_id bigint NOT NULL,
    status text NOT NULL,
    cloud_file_id text,
    cloud_file_name text,
    details_json text,
    started_at timestamp with time zone,
    finished_at timestamp with time zone
);


ALTER TABLE public.backup_runs OWNER TO fabouanes;

--
-- Name: backup_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.backup_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.backup_runs_id_seq OWNER TO fabouanes;

--
-- Name: backup_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.backup_runs_id_seq OWNED BY public.backup_runs.id;


--
-- Name: client_history; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.client_history (
    id integer NOT NULL,
    client_id integer NOT NULL,
    operation_date date NOT NULL,
    designation text DEFAULT ''::text NOT NULL,
    montant_achat numeric(15,4) DEFAULT 0 NOT NULL,
    montant_verse numeric(15,4) DEFAULT 0 NOT NULL,
    solde_cumule numeric(15,4) DEFAULT 0 NOT NULL,
    ordre_import integer DEFAULT 0 NOT NULL,
    source text DEFAULT 'import_excel'::text NOT NULL,
    sale_id integer,
    raw_sale_id integer,
    payment_id integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.client_history OWNER TO fabouanes;

--
-- Name: client_history_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.client_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.client_history_id_seq OWNER TO fabouanes;

--
-- Name: client_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.client_history_id_seq OWNED BY public.client_history.id;


--
-- Name: client_keys; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.client_keys (
    client_id bigint NOT NULL,
    encryption_key text NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.client_keys OWNER TO fabouanes;

--
-- Name: clients; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.clients (
    id bigint NOT NULL,
    name text NOT NULL,
    phone text,
    address text,
    notes text,
    opening_credit numeric(15,4) DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    search_vector tsvector
);


ALTER TABLE public.clients OWNER TO fabouanes;

--
-- Name: clients_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.clients_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.clients_id_seq OWNER TO fabouanes;

--
-- Name: clients_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.clients_id_seq OWNED BY public.clients.id;


--
-- Name: payments; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.payments (
    id bigint NOT NULL,
    client_id bigint NOT NULL,
    sale_id bigint,
    raw_sale_id bigint,
    sale_kind text,
    payment_type text DEFAULT 'versement'::text NOT NULL,
    allocation_meta text,
    amount numeric(15,4) NOT NULL,
    payment_date date NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.payments OWNER TO fabouanes;

--
-- Name: raw_sales; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.raw_sales (
    id bigint NOT NULL,
    client_id bigint,
    document_id bigint,
    raw_material_id bigint NOT NULL,
    quantity numeric(15,4) NOT NULL,
    unit text NOT NULL,
    unit_price numeric(15,4) NOT NULL,
    total numeric(15,4) NOT NULL,
    sale_type text NOT NULL,
    amount_paid numeric(15,4) DEFAULT 0 NOT NULL,
    balance_due numeric(15,4) DEFAULT 0 NOT NULL,
    cost_price_snapshot numeric(15,4) DEFAULT 0 NOT NULL,
    profit_amount numeric(15,4) DEFAULT 0 NOT NULL,
    sale_date date NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    custom_item_name text,
    CONSTRAINT raw_sales_sale_type_check CHECK ((sale_type = ANY (ARRAY['cash'::text, 'credit'::text])))
);


ALTER TABLE public.raw_sales OWNER TO fabouanes;

--
-- Name: sales; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.sales (
    id bigint NOT NULL,
    client_id bigint,
    document_id bigint,
    finished_product_id bigint NOT NULL,
    quantity numeric(15,4) NOT NULL,
    unit text NOT NULL,
    unit_price numeric(15,4) NOT NULL,
    total numeric(15,4) NOT NULL,
    sale_type text NOT NULL,
    amount_paid numeric(15,4) DEFAULT 0 NOT NULL,
    balance_due numeric(15,4) DEFAULT 0 NOT NULL,
    cost_price_snapshot numeric(15,4) DEFAULT 0 NOT NULL,
    profit_amount numeric(15,4) DEFAULT 0 NOT NULL,
    sale_date date NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sales_sale_type_check CHECK ((sale_type = ANY (ARRAY['cash'::text, 'credit'::text])))
);


ALTER TABLE public.sales OWNER TO fabouanes;

--
-- Name: clients_with_stats; Type: VIEW; Schema: public; Owner: fabouanes
--

CREATE VIEW public.clients_with_stats AS
 WITH finished_totals AS (
         SELECT sales.client_id,
            sum(sales.total) AS total_sales,
            sum(
                CASE
                    WHEN (sales.sale_type = 'credit'::text) THEN sales.total
                    ELSE (0)::numeric
                END) AS credit_total
           FROM public.sales
          WHERE (sales.client_id IS NOT NULL)
          GROUP BY sales.client_id
        ), raw_totals AS (
         SELECT raw_sales.client_id,
            sum(raw_sales.total) AS total_sales,
            sum(
                CASE
                    WHEN (raw_sales.sale_type = 'credit'::text) THEN raw_sales.total
                    ELSE (0)::numeric
                END) AS credit_total
           FROM public.raw_sales
          WHERE (raw_sales.client_id IS NOT NULL)
          GROUP BY raw_sales.client_id
        ), payment_totals AS (
         SELECT payments.client_id,
            sum(
                CASE
                    WHEN (payments.payment_type = 'versement'::text) THEN payments.amount
                    ELSE (0)::numeric
                END) AS versements,
            sum(
                CASE
                    WHEN (payments.payment_type = 'avance'::text) THEN payments.amount
                    ELSE (0)::numeric
                END) AS avances
           FROM public.payments
          GROUP BY payments.client_id
        )
 SELECT c.id,
    c.name,
    c.phone,
    c.address,
    c.notes,
    c.opening_credit,
    c.created_at,
    c.search_vector,
    ((((c.opening_credit + COALESCE(ft.credit_total, (0)::numeric)) + COALESCE(rt.credit_total, (0)::numeric)) - COALESCE(pt.versements, (0)::numeric)) + COALESCE(pt.avances, (0)::numeric)) AS current_debt,
    ((((c.opening_credit + COALESCE(ft.credit_total, (0)::numeric)) + COALESCE(rt.credit_total, (0)::numeric)) - COALESCE(pt.versements, (0)::numeric)) + COALESCE(pt.avances, (0)::numeric)) AS current_balance,
    (COALESCE(ft.total_sales, (0)::numeric) + COALESCE(rt.total_sales, (0)::numeric)) AS total_sales,
    COALESCE(pt.versements, (0)::numeric) AS total_payments
   FROM (((public.clients c
     LEFT JOIN finished_totals ft ON ((ft.client_id = c.id)))
     LEFT JOIN raw_totals rt ON ((rt.client_id = c.id)))
     LEFT JOIN payment_totals pt ON ((pt.client_id = c.id)));


ALTER VIEW public.clients_with_stats OWNER TO fabouanes;

--
-- Name: dead_letter_events; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.dead_letter_events (
    id bigint NOT NULL,
    event_type character varying(255) NOT NULL,
    payload text NOT NULL,
    reason text NOT NULL,
    failed_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.dead_letter_events OWNER TO fabouanes;

--
-- Name: dead_letter_events_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.dead_letter_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.dead_letter_events_id_seq OWNER TO fabouanes;

--
-- Name: dead_letter_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.dead_letter_events_id_seq OWNED BY public.dead_letter_events.id;


--
-- Name: error_logs; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.error_logs (
    id bigint NOT NULL,
    username text NOT NULL,
    route text,
    error_type text,
    message text,
    traceback text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.error_logs OWNER TO fabouanes;

--
-- Name: error_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.error_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.error_logs_id_seq OWNER TO fabouanes;

--
-- Name: error_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.error_logs_id_seq OWNED BY public.error_logs.id;


--
-- Name: expenses; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.expenses (
    id bigint NOT NULL,
    date date NOT NULL,
    category text DEFAULT 'general'::text NOT NULL,
    description text,
    amount double precision DEFAULT 0 NOT NULL,
    payment_method text DEFAULT 'cash'::text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT expenses_payment_method_check CHECK ((payment_method = ANY (ARRAY['cash'::text, 'cheque'::text, 'virement'::text, 'autre'::text])))
);


ALTER TABLE public.expenses OWNER TO fabouanes;

--
-- Name: expenses_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.expenses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.expenses_id_seq OWNER TO fabouanes;

--
-- Name: expenses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.expenses_id_seq OWNED BY public.expenses.id;


--
-- Name: finished_products; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.finished_products (
    id bigint NOT NULL,
    name text NOT NULL,
    default_unit text DEFAULT 'kg'::text NOT NULL,
    stock_qty numeric(15,4) DEFAULT 0 NOT NULL,
    sale_price numeric(15,4) DEFAULT 0 NOT NULL,
    avg_cost numeric(15,4) DEFAULT 0 NOT NULL,
    alert_threshold numeric(15,4) DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.finished_products OWNER TO fabouanes;

--
-- Name: finished_products_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.finished_products_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.finished_products_id_seq OWNER TO fabouanes;

--
-- Name: finished_products_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.finished_products_id_seq OWNED BY public.finished_products.id;


--
-- Name: idempotent_requests; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.idempotent_requests (
    key character varying(255) NOT NULL,
    response_json text NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.idempotent_requests OWNER TO fabouanes;

--
-- Name: imported_client_history; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.imported_client_history (
    id bigint NOT NULL,
    client_id bigint NOT NULL,
    source_file text,
    entry_date text NOT NULL,
    designation text,
    debit_amount numeric(15,4) DEFAULT 0 NOT NULL,
    credit_amount numeric(15,4) DEFAULT 0 NOT NULL,
    running_balance numeric(15,4) DEFAULT 0 NOT NULL,
    imported_by_user_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.imported_client_history OWNER TO fabouanes;

--
-- Name: imported_client_history_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.imported_client_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.imported_client_history_id_seq OWNER TO fabouanes;

--
-- Name: imported_client_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.imported_client_history_id_seq OWNED BY public.imported_client_history.id;


--
-- Name: mv_client_balances; Type: MATERIALIZED VIEW; Schema: public; Owner: fabouanes
--

CREATE MATERIALIZED VIEW public.mv_client_balances AS
 SELECT c.id AS client_id,
    c.name,
    ((((c.opening_credit + COALESCE(s_finished.total, (0)::numeric)) + COALESCE(s_raw.total, (0)::numeric)) - COALESCE(p_versement.total, (0)::numeric)) + COALESCE(p_avance.total, (0)::numeric)) AS balance
   FROM ((((public.clients c
     LEFT JOIN ( SELECT sales.client_id,
            sum(sales.total) AS total
           FROM public.sales
          WHERE (sales.sale_type = 'credit'::text)
          GROUP BY sales.client_id) s_finished ON ((s_finished.client_id = c.id)))
     LEFT JOIN ( SELECT raw_sales.client_id,
            sum(raw_sales.total) AS total
           FROM public.raw_sales
          WHERE (raw_sales.sale_type = 'credit'::text)
          GROUP BY raw_sales.client_id) s_raw ON ((s_raw.client_id = c.id)))
     LEFT JOIN ( SELECT payments.client_id,
            sum(payments.amount) AS total
           FROM public.payments
          WHERE (payments.payment_type = 'versement'::text)
          GROUP BY payments.client_id) p_versement ON ((p_versement.client_id = c.id)))
     LEFT JOIN ( SELECT payments.client_id,
            sum(payments.amount) AS total
           FROM public.payments
          WHERE (payments.payment_type = 'avance'::text)
          GROUP BY payments.client_id) p_avance ON ((p_avance.client_id = c.id)))
  WITH NO DATA;


ALTER MATERIALIZED VIEW public.mv_client_balances OWNER TO fabouanes;

--
-- Name: outbox_events; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.outbox_events (
    id bigint NOT NULL,
    event_type character varying(255) NOT NULL,
    payload text NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    processed_at timestamp with time zone,
    retry_count integer DEFAULT 0 NOT NULL,
    last_error text
);


ALTER TABLE public.outbox_events OWNER TO fabouanes;

--
-- Name: outbox_events_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.outbox_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.outbox_events_id_seq OWNER TO fabouanes;

--
-- Name: outbox_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.outbox_events_id_seq OWNED BY public.outbox_events.id;


--
-- Name: payments_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.payments_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.payments_id_seq OWNER TO fabouanes;

--
-- Name: payments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.payments_id_seq OWNED BY public.payments.id;


--
-- Name: performance_logs; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.performance_logs (
    id bigint NOT NULL,
    kind text NOT NULL,
    name text NOT NULL,
    elapsed_ms double precision DEFAULT 0 NOT NULL,
    route text,
    details text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.performance_logs OWNER TO fabouanes;

--
-- Name: performance_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.performance_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.performance_logs_id_seq OWNER TO fabouanes;

--
-- Name: performance_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.performance_logs_id_seq OWNED BY public.performance_logs.id;


--
-- Name: production_batch_items; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.production_batch_items (
    id bigint NOT NULL,
    batch_id bigint NOT NULL,
    raw_material_id bigint NOT NULL,
    quantity numeric(15,4) NOT NULL,
    unit_cost_snapshot numeric(15,4) DEFAULT 0 NOT NULL,
    line_cost numeric(15,4) DEFAULT 0 NOT NULL
);


ALTER TABLE public.production_batch_items OWNER TO fabouanes;

--
-- Name: production_batch_items_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.production_batch_items_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.production_batch_items_id_seq OWNER TO fabouanes;

--
-- Name: production_batch_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.production_batch_items_id_seq OWNED BY public.production_batch_items.id;


--
-- Name: production_batches; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.production_batches (
    id bigint NOT NULL,
    finished_product_id bigint NOT NULL,
    output_quantity numeric(15,4) NOT NULL,
    production_cost numeric(15,4) DEFAULT 0 NOT NULL,
    unit_cost numeric(15,4) DEFAULT 0 NOT NULL,
    production_date date NOT NULL,
    notes text
);


ALTER TABLE public.production_batches OWNER TO fabouanes;

--
-- Name: production_batches_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.production_batches_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.production_batches_id_seq OWNER TO fabouanes;

--
-- Name: production_batches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.production_batches_id_seq OWNED BY public.production_batches.id;


--
-- Name: purchase_documents; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.purchase_documents (
    id bigint NOT NULL,
    supplier_id bigint,
    doc_number text NOT NULL,
    total numeric(15,4) DEFAULT 0 NOT NULL,
    purchase_date date NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.purchase_documents OWNER TO fabouanes;

--
-- Name: purchase_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.purchase_documents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.purchase_documents_id_seq OWNER TO fabouanes;

--
-- Name: purchase_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.purchase_documents_id_seq OWNED BY public.purchase_documents.id;


--
-- Name: purchases; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.purchases (
    id bigint NOT NULL,
    supplier_id bigint,
    document_id bigint,
    raw_material_id bigint,
    finished_product_id bigint,
    quantity numeric(15,4) NOT NULL,
    unit text DEFAULT 'kg'::text NOT NULL,
    unit_price numeric(15,4) NOT NULL,
    total numeric(15,4) NOT NULL,
    purchase_date date NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    custom_item_name text
);


ALTER TABLE public.purchases OWNER TO fabouanes;

--
-- Name: purchases_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.purchases_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.purchases_id_seq OWNER TO fabouanes;

--
-- Name: purchases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.purchases_id_seq OWNED BY public.purchases.id;


--
-- Name: rate_limit_events; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.rate_limit_events (
    key text NOT NULL,
    hit_at timestamp with time zone NOT NULL
);


ALTER TABLE public.rate_limit_events OWNER TO fabouanes;

--
-- Name: raw_materials; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.raw_materials (
    id bigint NOT NULL,
    name text NOT NULL,
    unit text DEFAULT 'kg'::text NOT NULL,
    stock_qty numeric(15,4) DEFAULT 0 NOT NULL,
    avg_cost numeric(15,4) DEFAULT 0 NOT NULL,
    sale_price numeric(15,4) DEFAULT 0 NOT NULL,
    alert_threshold numeric(15,4) DEFAULT 0 NOT NULL,
    threshold_qty numeric(15,4) DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.raw_materials OWNER TO fabouanes;

--
-- Name: raw_materials_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.raw_materials_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.raw_materials_id_seq OWNER TO fabouanes;

--
-- Name: raw_materials_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.raw_materials_id_seq OWNED BY public.raw_materials.id;


--
-- Name: raw_sales_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.raw_sales_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.raw_sales_id_seq OWNER TO fabouanes;

--
-- Name: raw_sales_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.raw_sales_id_seq OWNED BY public.raw_sales.id;


--
-- Name: sale_documents; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.sale_documents (
    id bigint NOT NULL,
    client_id bigint,
    doc_number text NOT NULL,
    sale_type text NOT NULL,
    total numeric(15,4) DEFAULT 0 NOT NULL,
    amount_paid numeric(15,4) DEFAULT 0 NOT NULL,
    balance_due numeric(15,4) DEFAULT 0 NOT NULL,
    sale_date date NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sale_documents_sale_type_check CHECK ((sale_type = ANY (ARRAY['cash'::text, 'credit'::text])))
);


ALTER TABLE public.sale_documents OWNER TO fabouanes;

--
-- Name: sale_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.sale_documents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sale_documents_id_seq OWNER TO fabouanes;

--
-- Name: sale_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.sale_documents_id_seq OWNED BY public.sale_documents.id;


--
-- Name: sales_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.sales_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sales_id_seq OWNER TO fabouanes;

--
-- Name: sales_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.sales_id_seq OWNED BY public.sales.id;


--
-- Name: saved_recipe_items; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.saved_recipe_items (
    id bigint NOT NULL,
    recipe_id bigint NOT NULL,
    raw_material_id bigint NOT NULL,
    quantity numeric(15,4) NOT NULL,
    "position" integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.saved_recipe_items OWNER TO fabouanes;

--
-- Name: saved_recipe_items_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.saved_recipe_items_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.saved_recipe_items_id_seq OWNER TO fabouanes;

--
-- Name: saved_recipe_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.saved_recipe_items_id_seq OWNED BY public.saved_recipe_items.id;


--
-- Name: saved_recipes; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.saved_recipes (
    id bigint NOT NULL,
    finished_product_id bigint NOT NULL,
    name text NOT NULL,
    notes text,
    created_by_user_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.saved_recipes OWNER TO fabouanes;

--
-- Name: saved_recipes_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.saved_recipes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.saved_recipes_id_seq OWNER TO fabouanes;

--
-- Name: saved_recipes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.saved_recipes_id_seq OWNED BY public.saved_recipes.id;


--
-- Name: stock_alerts; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.stock_alerts (
    id bigint NOT NULL,
    product_type text NOT NULL,
    product_id bigint NOT NULL,
    product_name text NOT NULL,
    current_qty numeric(15,4) NOT NULL,
    threshold_qty numeric(15,4) NOT NULL,
    triggered_at timestamp with time zone DEFAULT now() NOT NULL,
    acknowledged_at timestamp with time zone
);


ALTER TABLE public.stock_alerts OWNER TO fabouanes;

--
-- Name: stock_alerts_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.stock_alerts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stock_alerts_id_seq OWNER TO fabouanes;

--
-- Name: stock_alerts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.stock_alerts_id_seq OWNED BY public.stock_alerts.id;


--
-- Name: stock_movements; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.stock_movements (
    id bigint NOT NULL,
    item_kind text NOT NULL,
    item_id bigint NOT NULL,
    direction text NOT NULL,
    quantity numeric(15,4) DEFAULT 0 NOT NULL,
    unit text,
    stock_before numeric(15,4) DEFAULT 0 NOT NULL,
    stock_after numeric(15,4) DEFAULT 0 NOT NULL,
    reason text,
    reference_type text,
    reference_id bigint,
    created_by_username text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.stock_movements OWNER TO fabouanes;

--
-- Name: stock_movements_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.stock_movements_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stock_movements_id_seq OWNER TO fabouanes;

--
-- Name: stock_movements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.stock_movements_id_seq OWNED BY public.stock_movements.id;


--
-- Name: suppliers; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.suppliers (
    id bigint NOT NULL,
    name text NOT NULL,
    phone text,
    address text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.suppliers OWNER TO fabouanes;

--
-- Name: suppliers_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.suppliers_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.suppliers_id_seq OWNER TO fabouanes;

--
-- Name: suppliers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.suppliers_id_seq OWNED BY public.suppliers.id;


--
-- Name: system_logs; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.system_logs (
    id bigint NOT NULL,
    level text NOT NULL,
    message text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.system_logs OWNER TO fabouanes;

--
-- Name: system_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.system_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.system_logs_id_seq OWNER TO fabouanes;

--
-- Name: system_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.system_logs_id_seq OWNED BY public.system_logs.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: fabouanes
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    username text NOT NULL,
    password_hash text NOT NULL,
    role text DEFAULT 'operator'::text,
    must_change_password boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    last_login_at timestamp with time zone,
    last_password_change_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_users_role CHECK ((role = ANY (ARRAY['admin'::text, 'operator'::text, 'manager'::text])))
);


ALTER TABLE public.users OWNER TO fabouanes;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: fabouanes
--

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO fabouanes;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fabouanes
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: activity_logs id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.activity_logs ALTER COLUMN id SET DEFAULT nextval('public.activity_logs_id_seq'::regclass);


--
-- Name: api_refresh_tokens id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.api_refresh_tokens ALTER COLUMN id SET DEFAULT nextval('public.api_refresh_tokens_id_seq'::regclass);


--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);


--
-- Name: backup_jobs id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.backup_jobs ALTER COLUMN id SET DEFAULT nextval('public.backup_jobs_id_seq'::regclass);


--
-- Name: backup_runs id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.backup_runs ALTER COLUMN id SET DEFAULT nextval('public.backup_runs_id_seq'::regclass);


--
-- Name: client_history id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.client_history ALTER COLUMN id SET DEFAULT nextval('public.client_history_id_seq'::regclass);


--
-- Name: clients id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.clients ALTER COLUMN id SET DEFAULT nextval('public.clients_id_seq'::regclass);


--
-- Name: dead_letter_events id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.dead_letter_events ALTER COLUMN id SET DEFAULT nextval('public.dead_letter_events_id_seq'::regclass);


--
-- Name: error_logs id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.error_logs ALTER COLUMN id SET DEFAULT nextval('public.error_logs_id_seq'::regclass);


--
-- Name: expenses id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.expenses ALTER COLUMN id SET DEFAULT nextval('public.expenses_id_seq'::regclass);


--
-- Name: finished_products id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.finished_products ALTER COLUMN id SET DEFAULT nextval('public.finished_products_id_seq'::regclass);


--
-- Name: imported_client_history id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.imported_client_history ALTER COLUMN id SET DEFAULT nextval('public.imported_client_history_id_seq'::regclass);


--
-- Name: outbox_events id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.outbox_events ALTER COLUMN id SET DEFAULT nextval('public.outbox_events_id_seq'::regclass);


--
-- Name: payments id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.payments ALTER COLUMN id SET DEFAULT nextval('public.payments_id_seq'::regclass);


--
-- Name: performance_logs id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.performance_logs ALTER COLUMN id SET DEFAULT nextval('public.performance_logs_id_seq'::regclass);


--
-- Name: production_batch_items id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.production_batch_items ALTER COLUMN id SET DEFAULT nextval('public.production_batch_items_id_seq'::regclass);


--
-- Name: production_batches id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.production_batches ALTER COLUMN id SET DEFAULT nextval('public.production_batches_id_seq'::regclass);


--
-- Name: purchase_documents id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.purchase_documents ALTER COLUMN id SET DEFAULT nextval('public.purchase_documents_id_seq'::regclass);


--
-- Name: purchases id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.purchases ALTER COLUMN id SET DEFAULT nextval('public.purchases_id_seq'::regclass);


--
-- Name: raw_materials id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.raw_materials ALTER COLUMN id SET DEFAULT nextval('public.raw_materials_id_seq'::regclass);


--
-- Name: raw_sales id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.raw_sales ALTER COLUMN id SET DEFAULT nextval('public.raw_sales_id_seq'::regclass);


--
-- Name: sale_documents id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.sale_documents ALTER COLUMN id SET DEFAULT nextval('public.sale_documents_id_seq'::regclass);


--
-- Name: sales id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.sales ALTER COLUMN id SET DEFAULT nextval('public.sales_id_seq'::regclass);


--
-- Name: saved_recipe_items id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.saved_recipe_items ALTER COLUMN id SET DEFAULT nextval('public.saved_recipe_items_id_seq'::regclass);


--
-- Name: saved_recipes id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.saved_recipes ALTER COLUMN id SET DEFAULT nextval('public.saved_recipes_id_seq'::regclass);


--
-- Name: stock_alerts id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.stock_alerts ALTER COLUMN id SET DEFAULT nextval('public.stock_alerts_id_seq'::regclass);


--
-- Name: stock_movements id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.stock_movements ALTER COLUMN id SET DEFAULT nextval('public.stock_movements_id_seq'::regclass);


--
-- Name: suppliers id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.suppliers ALTER COLUMN id SET DEFAULT nextval('public.suppliers_id_seq'::regclass);


--
-- Name: system_logs id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.system_logs ALTER COLUMN id SET DEFAULT nextval('public.system_logs_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: activity_logs activity_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.activity_logs
    ADD CONSTRAINT activity_logs_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: api_refresh_tokens api_refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.api_refresh_tokens
    ADD CONSTRAINT api_refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: api_refresh_tokens api_refresh_tokens_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.api_refresh_tokens
    ADD CONSTRAINT api_refresh_tokens_token_hash_key UNIQUE (token_hash);


--
-- Name: app_settings app_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_pkey PRIMARY KEY (key);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: backup_jobs backup_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.backup_jobs
    ADD CONSTRAINT backup_jobs_pkey PRIMARY KEY (id);


--
-- Name: backup_runs backup_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.backup_runs
    ADD CONSTRAINT backup_runs_pkey PRIMARY KEY (id);


--
-- Name: client_history client_history_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.client_history
    ADD CONSTRAINT client_history_pkey PRIMARY KEY (id);


--
-- Name: client_keys client_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.client_keys
    ADD CONSTRAINT client_keys_pkey PRIMARY KEY (client_id);


--
-- Name: clients clients_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_pkey PRIMARY KEY (id);


--
-- Name: dead_letter_events dead_letter_events_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.dead_letter_events
    ADD CONSTRAINT dead_letter_events_pkey PRIMARY KEY (id);


--
-- Name: error_logs error_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.error_logs
    ADD CONSTRAINT error_logs_pkey PRIMARY KEY (id);


--
-- Name: expenses expenses_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_pkey PRIMARY KEY (id);


--
-- Name: finished_products finished_products_name_key; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.finished_products
    ADD CONSTRAINT finished_products_name_key UNIQUE (name);


--
-- Name: finished_products finished_products_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.finished_products
    ADD CONSTRAINT finished_products_pkey PRIMARY KEY (id);


--
-- Name: idempotent_requests idempotent_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.idempotent_requests
    ADD CONSTRAINT idempotent_requests_pkey PRIMARY KEY (key);


--
-- Name: imported_client_history imported_client_history_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.imported_client_history
    ADD CONSTRAINT imported_client_history_pkey PRIMARY KEY (id);


--
-- Name: outbox_events outbox_events_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.outbox_events
    ADD CONSTRAINT outbox_events_pkey PRIMARY KEY (id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (id);


--
-- Name: performance_logs performance_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.performance_logs
    ADD CONSTRAINT performance_logs_pkey PRIMARY KEY (id);


--
-- Name: production_batch_items production_batch_items_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.production_batch_items
    ADD CONSTRAINT production_batch_items_pkey PRIMARY KEY (id);


--
-- Name: production_batches production_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT production_batches_pkey PRIMARY KEY (id);


--
-- Name: purchase_documents purchase_documents_doc_number_key; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.purchase_documents
    ADD CONSTRAINT purchase_documents_doc_number_key UNIQUE (doc_number);


--
-- Name: purchase_documents purchase_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.purchase_documents
    ADD CONSTRAINT purchase_documents_pkey PRIMARY KEY (id);


--
-- Name: purchases purchases_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.purchases
    ADD CONSTRAINT purchases_pkey PRIMARY KEY (id);


--
-- Name: raw_materials raw_materials_name_key; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.raw_materials
    ADD CONSTRAINT raw_materials_name_key UNIQUE (name);


--
-- Name: raw_materials raw_materials_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.raw_materials
    ADD CONSTRAINT raw_materials_pkey PRIMARY KEY (id);


--
-- Name: raw_sales raw_sales_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.raw_sales
    ADD CONSTRAINT raw_sales_pkey PRIMARY KEY (id);


--
-- Name: sale_documents sale_documents_doc_number_key; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.sale_documents
    ADD CONSTRAINT sale_documents_doc_number_key UNIQUE (doc_number);


--
-- Name: sale_documents sale_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.sale_documents
    ADD CONSTRAINT sale_documents_pkey PRIMARY KEY (id);


--
-- Name: sales sales_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_pkey PRIMARY KEY (id);


--
-- Name: saved_recipe_items saved_recipe_items_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.saved_recipe_items
    ADD CONSTRAINT saved_recipe_items_pkey PRIMARY KEY (id);


--
-- Name: saved_recipes saved_recipes_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.saved_recipes
    ADD CONSTRAINT saved_recipes_pkey PRIMARY KEY (id);


--
-- Name: stock_alerts stock_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.stock_alerts
    ADD CONSTRAINT stock_alerts_pkey PRIMARY KEY (id);


--
-- Name: stock_movements stock_movements_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_pkey PRIMARY KEY (id);


--
-- Name: suppliers suppliers_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.suppliers
    ADD CONSTRAINT suppliers_pkey PRIMARY KEY (id);


--
-- Name: system_logs system_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.system_logs
    ADD CONSTRAINT system_logs_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: idx_activity_logs_action; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_activity_logs_action ON public.activity_logs USING btree (action);


--
-- Name: idx_activity_logs_created_at; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_activity_logs_created_at ON public.activity_logs USING btree (created_at);


--
-- Name: idx_activity_logs_entity; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_activity_logs_entity ON public.activity_logs USING btree (entity_type, entity_id);


--
-- Name: idx_activity_logs_username; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_activity_logs_username ON public.activity_logs USING btree (username);


--
-- Name: idx_api_refresh_tokens_user; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_api_refresh_tokens_user ON public.api_refresh_tokens USING btree (user_id);


--
-- Name: idx_audit_logs_action; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_audit_logs_action ON public.audit_logs USING btree (action);


--
-- Name: idx_audit_logs_actor; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_audit_logs_actor ON public.audit_logs USING btree (actor_username);


--
-- Name: idx_audit_logs_actor_user_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_audit_logs_actor_user_id ON public.audit_logs USING btree (actor_user_id);


--
-- Name: idx_audit_logs_created_at; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_audit_logs_created_at ON public.audit_logs USING btree (created_at);


--
-- Name: idx_audit_logs_entity; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_audit_logs_entity ON public.audit_logs USING btree (entity_type, entity_id);


--
-- Name: idx_audit_logs_status; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_audit_logs_status ON public.audit_logs USING btree (status);


--
-- Name: idx_backup_jobs_status; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_backup_jobs_status ON public.backup_jobs USING btree (status);


--
-- Name: idx_backup_runs_job; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_backup_runs_job ON public.backup_runs USING btree (job_id);


--
-- Name: idx_ch_client_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_ch_client_id ON public.client_history USING btree (client_id);


--
-- Name: idx_ch_date; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_ch_date ON public.client_history USING btree (client_id, operation_date);


--
-- Name: idx_client_history_search; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_client_history_search ON public.client_history USING btree (client_id, operation_date DESC, id DESC);


--
-- Name: idx_clients_fts; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_clients_fts ON public.clients USING gin (search_vector);


--
-- Name: idx_clients_name; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_clients_name ON public.clients USING btree (name);


--
-- Name: idx_clients_phone; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_clients_phone ON public.clients USING btree (phone);


--
-- Name: idx_error_logs_created_at; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_error_logs_created_at ON public.error_logs USING btree (created_at);


--
-- Name: idx_finished_products_alert; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_finished_products_alert ON public.finished_products USING btree (stock_qty);


--
-- Name: idx_finished_products_name; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_finished_products_name ON public.finished_products USING btree (name);


--
-- Name: idx_mv_client_balances_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE UNIQUE INDEX idx_mv_client_balances_id ON public.mv_client_balances USING btree (client_id);


--
-- Name: idx_outbox_events_processed_at; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_outbox_events_processed_at ON public.outbox_events USING btree (processed_at);


--
-- Name: idx_payments_client_date; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_payments_client_date ON public.payments USING btree (client_id, payment_date DESC);


--
-- Name: idx_payments_client_date_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_payments_client_date_id ON public.payments USING btree (client_id, payment_date, id);


--
-- Name: idx_payments_client_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_payments_client_id ON public.payments USING btree (client_id);


--
-- Name: idx_payments_covering_daily; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_payments_covering_daily ON public.payments USING btree (payment_date, amount);


--
-- Name: idx_payments_covering_type_date; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_payments_covering_type_date ON public.payments USING btree (payment_type, payment_date, amount);


--
-- Name: idx_payments_date_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_payments_date_id ON public.payments USING btree (payment_date, id);


--
-- Name: idx_payments_raw_sale_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_payments_raw_sale_id ON public.payments USING btree (raw_sale_id);


--
-- Name: idx_payments_sale_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_payments_sale_id ON public.payments USING btree (sale_id);


--
-- Name: idx_payments_type_client; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_payments_type_client ON public.payments USING btree (payment_type, client_id);


--
-- Name: idx_performance_logs_created_at; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_performance_logs_created_at ON public.performance_logs USING btree (created_at);


--
-- Name: idx_prod_batch_date_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_prod_batch_date_id ON public.production_batches USING btree (production_date, id);


--
-- Name: idx_prod_batch_product_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_prod_batch_product_id ON public.production_batches USING btree (finished_product_id);


--
-- Name: idx_prod_items_batch_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_prod_items_batch_id ON public.production_batch_items USING btree (batch_id);


--
-- Name: idx_prod_items_material_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_prod_items_material_id ON public.production_batch_items USING btree (raw_material_id);


--
-- Name: idx_purchase_documents_date_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_purchase_documents_date_id ON public.purchase_documents USING btree (purchase_date, id);


--
-- Name: idx_purchase_documents_supplier_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_purchase_documents_supplier_id ON public.purchase_documents USING btree (supplier_id);


--
-- Name: idx_purchases_covering_daily; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_purchases_covering_daily ON public.purchases USING btree (purchase_date, total);


--
-- Name: idx_purchases_date_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_purchases_date_id ON public.purchases USING btree (purchase_date, id);


--
-- Name: idx_purchases_document_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_purchases_document_id ON public.purchases USING btree (document_id, id);


--
-- Name: idx_purchases_finished_product_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_purchases_finished_product_id ON public.purchases USING btree (finished_product_id);


--
-- Name: idx_purchases_material; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_purchases_material ON public.purchases USING btree (raw_material_id, purchase_date DESC);


--
-- Name: idx_purchases_raw_material_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_purchases_raw_material_id ON public.purchases USING btree (raw_material_id);


--
-- Name: idx_purchases_supplier_date; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_purchases_supplier_date ON public.purchases USING btree (supplier_id, purchase_date);


--
-- Name: idx_purchases_supplier_date_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_purchases_supplier_date_id ON public.purchases USING btree (supplier_id, purchase_date, id);


--
-- Name: idx_purchases_supplier_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_purchases_supplier_id ON public.purchases USING btree (supplier_id);


--
-- Name: idx_rate_limit_events_key_hit_at; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_rate_limit_events_key_hit_at ON public.rate_limit_events USING btree (key, hit_at);


--
-- Name: idx_raw_materials_alert; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_materials_alert ON public.raw_materials USING btree (stock_qty, alert_threshold);


--
-- Name: idx_raw_materials_name; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_materials_name ON public.raw_materials USING btree (name);


--
-- Name: idx_raw_materials_stock_alert; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_materials_stock_alert ON public.raw_materials USING btree (stock_qty, alert_threshold);


--
-- Name: idx_raw_sales_client_date; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_sales_client_date ON public.raw_sales USING btree (client_id, sale_date DESC);


--
-- Name: idx_raw_sales_client_date_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_sales_client_date_id ON public.raw_sales USING btree (client_id, sale_date, id);


--
-- Name: idx_raw_sales_client_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_sales_client_id ON public.raw_sales USING btree (client_id);


--
-- Name: idx_raw_sales_covering_daily; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_sales_covering_daily ON public.raw_sales USING btree (sale_date, total, profit_amount);


--
-- Name: idx_raw_sales_covering_type_date; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_sales_covering_type_date ON public.raw_sales USING btree (sale_type, sale_date, total);


--
-- Name: idx_raw_sales_credit_client; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_sales_credit_client ON public.raw_sales USING btree (client_id, total) WHERE (sale_type = 'credit'::text);


--
-- Name: idx_raw_sales_date_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_sales_date_id ON public.raw_sales USING btree (sale_date, id);


--
-- Name: idx_raw_sales_document_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_sales_document_id ON public.raw_sales USING btree (document_id, id);


--
-- Name: idx_raw_sales_material_date; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_sales_material_date ON public.raw_sales USING btree (raw_material_id, sale_date);


--
-- Name: idx_raw_sales_material_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_sales_material_id ON public.raw_sales USING btree (raw_material_id);


--
-- Name: idx_raw_sales_reporting_composite; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_sales_reporting_composite ON public.raw_sales USING btree (raw_material_id, sale_date DESC, client_id);


--
-- Name: idx_raw_sales_sale_date; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_sales_sale_date ON public.raw_sales USING btree (sale_date);


--
-- Name: idx_raw_sales_type_date; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_raw_sales_type_date ON public.raw_sales USING btree (sale_type, sale_date);


--
-- Name: idx_sale_documents_client_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sale_documents_client_id ON public.sale_documents USING btree (client_id);


--
-- Name: idx_sale_documents_date_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sale_documents_date_id ON public.sale_documents USING btree (sale_date, id);


--
-- Name: idx_sales_client_date; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_client_date ON public.sales USING btree (client_id, sale_date DESC);


--
-- Name: idx_sales_client_date_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_client_date_id ON public.sales USING btree (client_id, sale_date, id);


--
-- Name: idx_sales_client_date_type; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_client_date_type ON public.sales USING btree (client_id, sale_date, sale_type);


--
-- Name: idx_sales_client_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_client_id ON public.sales USING btree (client_id);


--
-- Name: idx_sales_covering_daily; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_covering_daily ON public.sales USING btree (sale_date, total, profit_amount);


--
-- Name: idx_sales_covering_type_date; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_covering_type_date ON public.sales USING btree (sale_type, sale_date, total);


--
-- Name: idx_sales_credit_client; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_credit_client ON public.sales USING btree (client_id, total) WHERE (sale_type = 'credit'::text);


--
-- Name: idx_sales_date_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_date_id ON public.sales USING btree (sale_date, id);


--
-- Name: idx_sales_document_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_document_id ON public.sales USING btree (document_id, id);


--
-- Name: idx_sales_finished_product_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_finished_product_id ON public.sales USING btree (finished_product_id);


--
-- Name: idx_sales_product; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_product ON public.sales USING btree (finished_product_id, sale_date DESC);


--
-- Name: idx_sales_reporting_composite; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_reporting_composite ON public.sales USING btree (finished_product_id, sale_date DESC, client_id);


--
-- Name: idx_sales_sale_date; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_sale_date ON public.sales USING btree (sale_date);


--
-- Name: idx_sales_type_date; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_sales_type_date ON public.sales USING btree (sale_type, sale_date);


--
-- Name: idx_saved_recipe_items_material_id; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_saved_recipe_items_material_id ON public.saved_recipe_items USING btree (raw_material_id);


--
-- Name: idx_saved_recipe_items_recipe; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_saved_recipe_items_recipe ON public.saved_recipe_items USING btree (recipe_id);


--
-- Name: idx_saved_recipes_product; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_saved_recipes_product ON public.saved_recipes USING btree (finished_product_id);


--
-- Name: idx_stock_alerts_product; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_stock_alerts_product ON public.stock_alerts USING btree (product_type, product_id);


--
-- Name: idx_stock_alerts_triggered_at; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_stock_alerts_triggered_at ON public.stock_alerts USING btree (triggered_at);


--
-- Name: idx_suppliers_name; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_suppliers_name ON public.suppliers USING btree (name);


--
-- Name: idx_suppliers_phone; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_suppliers_phone ON public.suppliers USING btree (phone);


--
-- Name: idx_system_logs_created_at; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_system_logs_created_at ON public.system_logs USING btree (created_at);


--
-- Name: idx_users_role; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_users_role ON public.users USING btree (role);


--
-- Name: idx_users_username; Type: INDEX; Schema: public; Owner: fabouanes
--

CREATE INDEX idx_users_username ON public.users USING btree (username);


--
-- Name: clients trg_clients_fts; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_clients_fts BEFORE INSERT OR UPDATE ON public.clients FOR EACH ROW EXECUTE FUNCTION public.update_clients_search_vector();


--
-- Name: clients trg_clients_updated_at; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_clients_updated_at BEFORE UPDATE ON public.clients FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: finished_products trg_finished_products_updated_at; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_finished_products_updated_at BEFORE UPDATE ON public.finished_products FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: payments trg_payments_updated_at; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_payments_updated_at BEFORE UPDATE ON public.payments FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: purchase_documents trg_purchase_documents_updated_at; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_purchase_documents_updated_at BEFORE UPDATE ON public.purchase_documents FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: purchases trg_purchases_updated_at; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_purchases_updated_at BEFORE UPDATE ON public.purchases FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: raw_materials trg_raw_materials_updated_at; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_raw_materials_updated_at BEFORE UPDATE ON public.raw_materials FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: raw_sales trg_raw_sales_updated_at; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_raw_sales_updated_at BEFORE UPDATE ON public.raw_sales FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: sale_documents trg_sale_documents_updated_at; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_sale_documents_updated_at BEFORE UPDATE ON public.sale_documents FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: sales trg_sales_updated_at; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_sales_updated_at BEFORE UPDATE ON public.sales FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: suppliers trg_suppliers_updated_at; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_suppliers_updated_at BEFORE UPDATE ON public.suppliers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: payments trg_sync_payment_to_history; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_sync_payment_to_history AFTER INSERT OR DELETE OR UPDATE ON public.payments FOR EACH ROW EXECUTE FUNCTION public.sync_payment_to_client_history();


--
-- Name: raw_sales trg_sync_raw_sale_to_history; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_sync_raw_sale_to_history AFTER INSERT OR DELETE OR UPDATE ON public.raw_sales FOR EACH ROW EXECUTE FUNCTION public.sync_raw_sale_to_client_history();


--
-- Name: sales trg_sync_sale_to_history; Type: TRIGGER; Schema: public; Owner: fabouanes
--

CREATE TRIGGER trg_sync_sale_to_history AFTER INSERT OR DELETE OR UPDATE ON public.sales FOR EACH ROW EXECUTE FUNCTION public.sync_sale_to_client_history();


--
-- Name: api_refresh_tokens api_refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.api_refresh_tokens
    ADD CONSTRAINT api_refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: audit_logs audit_logs_actor_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_actor_user_id_fkey FOREIGN KEY (actor_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: backup_jobs backup_jobs_requested_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.backup_jobs
    ADD CONSTRAINT backup_jobs_requested_by_user_id_fkey FOREIGN KEY (requested_by_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: backup_runs backup_runs_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.backup_runs
    ADD CONSTRAINT backup_runs_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.backup_jobs(id) ON DELETE CASCADE;


--
-- Name: client_history client_history_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.client_history
    ADD CONSTRAINT client_history_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: purchases fk_purchases_document; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.purchases
    ADD CONSTRAINT fk_purchases_document FOREIGN KEY (document_id) REFERENCES public.purchase_documents(id) ON DELETE RESTRICT;


--
-- Name: sales fk_sales_document; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT fk_sales_document FOREIGN KEY (document_id) REFERENCES public.sale_documents(id) ON DELETE RESTRICT;


--
-- Name: imported_client_history imported_client_history_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.imported_client_history
    ADD CONSTRAINT imported_client_history_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: imported_client_history imported_client_history_imported_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.imported_client_history
    ADD CONSTRAINT imported_client_history_imported_by_user_id_fkey FOREIGN KEY (imported_by_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: payments payments_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: payments payments_raw_sale_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_raw_sale_id_fkey FOREIGN KEY (raw_sale_id) REFERENCES public.raw_sales(id) ON DELETE SET NULL;


--
-- Name: payments payments_sale_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_sale_id_fkey FOREIGN KEY (sale_id) REFERENCES public.sales(id) ON DELETE SET NULL;


--
-- Name: production_batch_items production_batch_items_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.production_batch_items
    ADD CONSTRAINT production_batch_items_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.production_batches(id) ON DELETE CASCADE;


--
-- Name: production_batch_items production_batch_items_raw_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.production_batch_items
    ADD CONSTRAINT production_batch_items_raw_material_id_fkey FOREIGN KEY (raw_material_id) REFERENCES public.raw_materials(id) ON DELETE CASCADE;


--
-- Name: production_batches production_batches_finished_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT production_batches_finished_product_id_fkey FOREIGN KEY (finished_product_id) REFERENCES public.finished_products(id) ON DELETE CASCADE;


--
-- Name: purchase_documents purchase_documents_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.purchase_documents
    ADD CONSTRAINT purchase_documents_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id) ON DELETE SET NULL;


--
-- Name: purchases purchases_finished_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.purchases
    ADD CONSTRAINT purchases_finished_product_id_fkey FOREIGN KEY (finished_product_id) REFERENCES public.finished_products(id) ON DELETE CASCADE;


--
-- Name: purchases purchases_raw_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.purchases
    ADD CONSTRAINT purchases_raw_material_id_fkey FOREIGN KEY (raw_material_id) REFERENCES public.raw_materials(id) ON DELETE CASCADE;


--
-- Name: purchases purchases_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.purchases
    ADD CONSTRAINT purchases_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id) ON DELETE SET NULL;


--
-- Name: raw_sales raw_sales_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.raw_sales
    ADD CONSTRAINT raw_sales_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE SET NULL;


--
-- Name: raw_sales raw_sales_raw_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.raw_sales
    ADD CONSTRAINT raw_sales_raw_material_id_fkey FOREIGN KEY (raw_material_id) REFERENCES public.raw_materials(id) ON DELETE CASCADE;


--
-- Name: sale_documents sale_documents_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.sale_documents
    ADD CONSTRAINT sale_documents_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE SET NULL;


--
-- Name: sales sales_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE SET NULL;


--
-- Name: sales sales_finished_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_finished_product_id_fkey FOREIGN KEY (finished_product_id) REFERENCES public.finished_products(id) ON DELETE CASCADE;


--
-- Name: saved_recipe_items saved_recipe_items_raw_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.saved_recipe_items
    ADD CONSTRAINT saved_recipe_items_raw_material_id_fkey FOREIGN KEY (raw_material_id) REFERENCES public.raw_materials(id) ON DELETE CASCADE;


--
-- Name: saved_recipe_items saved_recipe_items_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.saved_recipe_items
    ADD CONSTRAINT saved_recipe_items_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.saved_recipes(id) ON DELETE CASCADE;


--
-- Name: saved_recipes saved_recipes_created_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.saved_recipes
    ADD CONSTRAINT saved_recipes_created_by_user_id_fkey FOREIGN KEY (created_by_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: saved_recipes saved_recipes_finished_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fabouanes
--

ALTER TABLE ONLY public.saved_recipes
    ADD CONSTRAINT saved_recipes_finished_product_id_fkey FOREIGN KEY (finished_product_id) REFERENCES public.finished_products(id) ON DELETE CASCADE;


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: fabouanes
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- PostgreSQL database dump complete
--

\unrestrict s2AtQmzyLT2cmplwLt66oPAni0miz6A5ZCvqP6WqD6J9fed2FgE670Z5eJrY6Vn

