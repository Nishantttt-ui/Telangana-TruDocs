import { useState } from "react";
import Typeahead from "../../components/common/Typeahead.jsx";
import StatusMessage from "../../components/common/StatusMessage.jsx";
import LoaderModal from "../../components/common/LoaderModal.jsx";
import useOwnershipChain, {
  FILTER_OPTIONS,
  MAX_FILTERS,
} from "./useOwnershipChain.js";

const UNIT_FILTERS = new Set(['flat', 'villa', 'plot', 'door']);

function toIndianCurrency(str) {
  if (!str || str === "—") return str;
  const digits = str.replace(/[^\d.]/g, "");
  const num = parseFloat(digits);
  if (isNaN(num)) return str;
  return "₹" + num.toLocaleString("en-IN");
}

function ChainNode({ node, isLast }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails =
    (node.sellers && node.sellers.length > 0) ||
    (node.buyers && node.buyers.length > 0) ||
    !!node.propertySchedule;

  const price =
    node.consideration && node.consideration !== "—"
      ? toIndianCurrency(node.consideration)
      : null;

  return (
    <div className="chain-node">
      <div className="chain-node-spine">
        <div className="chain-node-dot" />
        {!isLast && <div className="chain-node-line" />}
      </div>
      <div className="chain-node-content">
        <div className="chain-node-doc">{node.article || "Transaction"}</div>
        {node.documentRef && (
          <div className="chain-node-ref">{node.documentRef}</div>
        )}
        {node.date && <div className="chain-node-date">{node.date}</div>}
        {price && <div className="chain-node-price">{price}</div>}
        {node.sroName && (
          <div className="chain-node-sro">{node.sroName}</div>
        )}
        {hasDetails && (
          <>
            <button
              type="button"
              className="chain-read-more"
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? "Read Less ▲" : "Read More ▼"}
            </button>
            {expanded && (
              <div className="chain-node-details">
                {node.sellers && node.sellers.length > 0 && (
                  <div className="chain-node-party-row">
                    <span className="chain-party-label">Seller</span>
                    <span>{node.sellers.join(", ")}</span>
                  </div>
                )}
                {node.buyers && node.buyers.length > 0 && (
                  <div className="chain-node-party-row">
                    <span className="chain-party-label">Buyer</span>
                    <span>{node.buyers.join(", ")}</span>
                  </div>
                )}
                {node.propertySchedule && (
                  <div className="chain-node-schedule">
                    {node.propertySchedule}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ChainTimeline({ chain, startParty }) {
  if (!chain || chain.length === 0)
    return (
      <p style={{ color: "var(--text-faint)", fontSize: 13 }}>
        No chain data available.
      </p>
    );

  // Most recent transaction is first (sorted date-desc).
  // If it's a forward hop (startParty sold the property), the buyer is the current owner.
  const latest = chain[0];
  const currentOwner =
    latest?.direction === "forward" && latest?.buyers?.length > 0
      ? latest.buyers[0]
      : startParty;

  return (
    <div className="chain-timeline">
      {currentOwner && (
        <div className="chain-current">
          <div className="chain-current-label">Current Owner</div>
          <div className="chain-current-name">{currentOwner}</div>
        </div>
      )}
      {chain.map((node, i) => (
        <ChainNode key={i} node={node} isLast={i === chain.length - 1} />
      ))}
    </div>
  );
}


export default function OwnershipChainView() {
  const {
    filterVillages,
    villageInput,
    setVillageInput,
    handleVillageSelect,
    handleVillageClear,
    partyName,
    setPartyName,
    filters,
    addFilter,
    removeFilter,
    updateFilter,
    status,
    loading,
    chainData,
    submit,
    cancelSearch,
  } = useOwnershipChain();

  function handleSubmit(e) {
    e.preventDefault();
    submit();
  }

  const availableTypes = FILTER_OPTIONS.filter(
    (o) => !filters.find((f) => f.filterType === o.value),
  );

  return (
    <div className="page">
      <div className="page-heading">
        <div className="page-badge">
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "#7c4a1a",
              display: "inline-block",
            }}
          />
          Title Search
        </div>
        <h1 className="page-title">Ownership Chain</h1>
        <p className="page-subtitle">
          Trace the complete chain of ownership for a property
        </p>
        <ul className="page-features">
          <li>Traces ownership back through all transactions</li>
          <li>Detects developer origin automatically</li>
          <li>Works across dual-property scenarios</li>
        </ul>
      </div>

      <div className="card" style={{ padding: "24px" }}>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>
              Village <span className="req">*</span>
            </label>
            <Typeahead
              items={[]}
              filterFn={filterVillages}
              value={villageInput}
              onChange={setVillageInput}
              onSelect={handleVillageSelect}
              onClear={handleVillageClear}
              placeholder="Search village name…"
            />
          </div>

          <div className="field">
            <label>
              Party Name <span className="req">*</span>
            </label>
            <input
              type="text"
              value={partyName}
              onChange={(e) => setPartyName(e.target.value)}
              placeholder="Current owner's name"
            />
          </div>

          <div className="field">
            <label>
              Property Filters{" "}
              <span
                style={{
                  fontWeight: 400,
                  color: "var(--text-faint)",
                  fontSize: 12,
                }}
              >
                (optional, max {MAX_FILTERS})
              </span>
            </label>
            {filters.length > 0 && (
              <div className="filter-rows">
                {filters.map((f, idx) => (
                  <div key={idx} className="filter-row">
                    <select
                      value={f.filterType}
                      onChange={(e) =>
                        updateFilter(idx, "filterType", e.target.value)
                      }
                    >
                      {FILTER_OPTIONS.map((o) => (
                        <option
                          key={o.value}
                          value={o.value}
                          disabled={
                            filters.findIndex(
                              (ff, ii) => ii !== idx && ff.filterType === o.value,
                            ) >= 0
                            ||
                            (UNIT_FILTERS.has(o.value) &&
                              filters.some(
                                (ff, ii) => ii !== idx && UNIT_FILTERS.has(ff.filterType),
                              ))
                          }
                        >
                          {o.label}
                        </option>
                      ))}
                    </select>
                    <input
                      type="text"
                      value={f.value}
                      onChange={(e) =>
                        updateFilter(idx, "value", e.target.value)
                      }
                      placeholder={`Enter ${FILTER_OPTIONS.find((o) => o.value === f.filterType)?.label || "value"}`}
                    />
                    <button
                      type="button"
                      className="filter-row-remove"
                      onClick={() => removeFilter(idx)}
                      aria-label="Remove filter"
                    >
                      <i className="ti ti-x" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <button
              type="button"
              className="add-filter-btn"
              onClick={addFilter}
              disabled={
                filters.length >= MAX_FILTERS || availableTypes.length === 0
              }
            >
              <i className="ti ti-plus" /> Add filter
            </button>
          </div>

          {status && (
            <div style={{ marginBottom: 12 }}>
              <StatusMessage kind={status.kind} message={status.message} />
            </div>
          )}

          <button type="submit" className="submit-btn" disabled={loading}>
            {loading ? (
              <>
                <i
                  className="ti ti-loader"
                  style={{ animation: "spin 1s linear infinite" }}
                />{" "}
                Tracing…
              </>
            ) : (
              <>
                <i className="ti ti-git-branch" /> Trace Ownership Chain
              </>
            )}
          </button>
        </form>
      </div>

      {chainData && (
        <div className="card" style={{ padding: "24px", marginTop: 20 }}>
          <h3
            style={{
              margin: "0 0 4px",
              fontFamily: "var(--font-display)",
              fontSize: 16,
              fontWeight: 600,
            }}
          >
            Ownership Chain
          </h3>
          <p
            style={{
              margin: "0 0 16px",
              fontSize: 13,
              color: "var(--text-faint)",
            }}
          >
            {chainData.status === "dual_chain"
              ? (chainData.chains || []).reduce(
                  (s, p) => s + (p.chain?.length || 0),
                  0,
                )
              : chainData.chain?.length || 0}{" "}
            transaction(s) found
          </p>

          {chainData.status === "too_many_properties" ? (
            <div className="chain-too-many">{status?.message}</div>
          ) : chainData.status === "dual_chain" ? (
            <div className="chain-dual-grid">
              {(chainData.chains || []).map((prop, i) => (
                <div key={i}>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 700,
                      color: "var(--text)",
                      marginBottom: 12,
                      paddingBottom: 8,
                      borderBottom: "2px solid var(--primary)",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <span
                      style={{
                        background: "var(--primary)",
                        color: "#fff",
                        borderRadius: 4,
                        padding: "2px 8px",
                        fontSize: 11,
                        fontWeight: 800,
                        letterSpacing: "0.04em",
                      }}
                    >
                      {i + 1}
                    </span>
                    {prop.propertyTypeLabel || "Property"}{" "}
                    {prop.propertyNo || ""}
                  </div>
                  <ChainTimeline
                    chain={prop.chain}
                    startParty={chainData.startParty}
                  />
                </div>
              ))}
            </div>
          ) : (
            <ChainTimeline
              chain={chainData.chain}
              startParty={chainData.startParty}
            />
          )}
        </div>
      )}

      <LoaderModal
        visible={loading}
        onCancel={cancelSearch}
        title="Tracing ownership chain…"
      />
    </div>
  );
}
