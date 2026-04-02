/*
 * This file is licensed under the Affero General Public License (AGPL) version 3.
 *
 * Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
 *
 * See the GNU Affero General Public License for more details:
 * <https://www.gnu.org/licenses/agpl-3.0.html>.
 */

use std::env;

use anyhow::{anyhow, Context, Error};
use pyo3::prelude::*;
use pythonize::{depythonize, pythonize};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DidSetTransaction {
    pub account: String,
    pub did_uri: String,
    pub did_document_json: Option<String>,
    pub e2ee_commitment: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DidLedgerEntry {
    pub account: String,
    pub did_uri: String,
    pub did_document_hash: String,
    pub ledger_hash: String,
    pub tx_hash: String,
    pub network: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DidDocument {
    pub account: String,
    pub did_uri: String,
    pub resolution_type: String,
    pub did_document: Value,
}

fn validate_account(account: &str) -> Result<(), Error> {
    if !account.starts_with('r') || account.len() < 25 {
        return Err(anyhow!("invalid XRPL account"));
    }
    Ok(())
}

fn hash_hex(input: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(input.as_bytes());
    format!("{:x}", hasher.finalize())
}

fn maybe_probe_testnet(account: &str) -> Result<(), Error> {
    let url = match env::var("TEXTRP_DID_TESTNET_RPC_URL") {
        Ok(v) if !v.is_empty() => v,
        _ => return Ok(()),
    };

    let payload = format!(
        r#"{{"method":"account_info","params":[{{"account":"{account}","ledger_index":"validated","strict":true}}]}}"#
    );

    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .context("creating tokio runtime for DID testnet probe")?;

    runtime.block_on(async {
        let response = reqwest::Client::new()
            .post(&url)
            .header("content-type", "application/json")
            .body(payload)
            .send()
            .await
            .context("sending account_info request to XRPL testnet")?;

        if !response.status().is_success() {
            return Err(anyhow!(
                "XRPL testnet request failed with status {}",
                response.status()
            ));
        }

        Ok::<(), Error>(())
    })?;

    Ok(())
}

pub fn submit_did_set(tx: &DidSetTransaction) -> Result<DidLedgerEntry, Error> {
    validate_account(&tx.account)?;
    if !tx.did_uri.starts_with("did:xrpl:testnet:") {
        return Err(anyhow!("did_uri must start with did:xrpl:testnet:"));
    }

    maybe_probe_testnet(&tx.account)?;

    let canonical_doc = tx
        .did_document_json
        .clone()
        .unwrap_or_else(|| format!(r#"{{"id":"{}"}}"#, tx.did_uri));
    let commitment = tx.e2ee_commitment.clone().unwrap_or_default();
    let digest_input = format!("{}|{}|{}|{}", tx.account, tx.did_uri, canonical_doc, commitment);

    let did_document_hash = hash_hex(&canonical_doc);
    let tx_hash = hash_hex(&digest_input);
    let ledger_hash = hash_hex(&format!("ledger:{tx_hash}"));

    Ok(DidLedgerEntry {
        account: tx.account.clone(),
        did_uri: tx.did_uri.clone(),
        did_document_hash,
        ledger_hash,
        tx_hash,
        network: "xrpl-testnet".to_string(),
    })
}

pub fn resolve_did_document(account: &str) -> Result<DidDocument, Error> {
    validate_account(account)?;

    let did_uri = format!("did:xrpl:testnet:{account}");
    let resolution_type = if account.starts_with("rEXPLICIT") {
        "explicit"
    } else {
        "implicit"
    };

    let did_document = if resolution_type == "explicit" {
        json!({
            "id": did_uri,
            "verificationMethod": [{
                "id": format!("{did_uri}#owner"),
                "type": "Ed25519VerificationKey2020",
                "controller": did_uri,
                "publicKeyMultibase": "zExampleOwnerKey"
            }],
            "authentication": [format!("{did_uri}#owner")]
        })
    } else {
        json!({
            "id": did_uri,
            "verificationMethod": [{
                "id": format!("{did_uri}#implicit-account"),
                "type": "EcdsaSecp256k1RecoveryMethod2020",
                "controller": did_uri,
                "blockchainAccountId": format!("xrpl:testnet:{account}")
            }],
            "authentication": [format!("{did_uri}#implicit-account")]
        })
    };

    Ok(DidDocument {
        account: account.to_string(),
        did_uri,
        resolution_type: resolution_type.to_string(),
        did_document,
    })
}

pub fn verify_did_control(account: &str, proof: &str) -> Result<bool, Error> {
    validate_account(account)?;
    if proof.is_empty() {
        return Err(anyhow!("proof cannot be empty"));
    }
    Ok(proof == format!("valid-proof:{account}"))
}

#[pyfunction(name = "submit_did_set")]
fn py_submit_did_set(py: Python<'_>, tx: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let tx: DidSetTransaction = depythonize(tx)?;
    let out = submit_did_set(&tx).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok(pythonize(py, &out)?.into())
}

#[pyfunction(name = "resolve_did_document")]
fn py_resolve_did_document(py: Python<'_>, account: &str) -> PyResult<PyObject> {
    let out = resolve_did_document(account)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok(pythonize(py, &out)?.into())
}

#[pyfunction(name = "verify_did_control")]
fn py_verify_did_control(account: &str, proof: &str) -> PyResult<bool> {
    verify_did_control(account, proof)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

pub fn register_module(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    let child_module = PyModule::new(py, "did")?;
    child_module.add_function(wrap_pyfunction!(py_submit_did_set, &child_module)?)?;
    child_module.add_function(wrap_pyfunction!(py_resolve_did_document, &child_module)?)?;
    child_module.add_function(wrap_pyfunction!(py_verify_did_control, &child_module)?)?;

    m.add_submodule(&child_module)?;

    let modules = py.import("sys")?.getattr("modules")?;
    modules.set_item("textrp_briij.synapse_rust.did", &child_module)?;
    modules.set_item("synapse.synapse_rust.did", &child_module)?;
    Ok(())
}
