-- Garantias de aprovacao humana no banco (ADR-006): defesa em profundidade alem do caso de uso.

-- 1. So se decide sobre sugestao pendente.
CREATE FUNCTION decisions_require_pending() RETURNS trigger AS $$
BEGIN
    IF (SELECT status FROM suggestions WHERE id = NEW.suggestion_id) IS DISTINCT FROM 'pending_review' THEN
        RAISE EXCEPTION 'a decision requires a pending_review suggestion'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER decisions_require_pending_trg
    BEFORE INSERT ON decisions
    FOR EACH ROW EXECUTE FUNCTION decisions_require_pending();

-- 2. Decisoes sao imutaveis.
CREATE FUNCTION decisions_block_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'decisions are immutable (% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER decisions_no_update_delete
    BEFORE UPDATE OR DELETE ON decisions
    FOR EACH ROW EXECUTE FUNCTION decisions_block_mutation();

-- 3. Status so anda para a frente: pending_review -> approved | rejected. refused e final.
CREATE FUNCTION suggestions_status_forward_only() RETURNS trigger AS $$
BEGIN
    IF OLD.status <> 'pending_review' AND NEW.status <> OLD.status THEN
        RAISE EXCEPTION 'suggestion status % is final', OLD.status
            USING ERRCODE = 'check_violation';
    END IF;
    IF OLD.status = 'pending_review' AND NEW.status = 'refused' THEN
        RAISE EXCEPTION 'a pending suggestion cannot become refused'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER suggestions_status_forward_only_trg
    BEFORE UPDATE OF status ON suggestions
    FOR EACH ROW EXECUTE FUNCTION suggestions_status_forward_only();

-- 4. approved/rejected exigem decisao humana correspondente. Verificado no COMMIT (deferido),
--    para permitir inserir a decisao e atualizar o status na mesma transacao.
CREATE FUNCTION suggestions_final_needs_decision() RETURNS trigger AS $$
BEGIN
    IF NEW.status IN ('approved', 'rejected') AND NOT EXISTS (
        SELECT 1 FROM decisions d
        WHERE d.suggestion_id = NEW.id
          AND d.outcome = CASE NEW.status WHEN 'approved' THEN 'approve' ELSE 'reject' END
    ) THEN
        RAISE EXCEPTION 'status % requires a matching human decision', NEW.status
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER suggestions_final_needs_decision_trg
    AFTER INSERT OR UPDATE OF status ON suggestions
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION suggestions_final_needs_decision();
