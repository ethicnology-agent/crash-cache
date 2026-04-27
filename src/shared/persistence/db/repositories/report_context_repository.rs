use super::{DbConnection, DbPool};
use diesel::prelude::*;

use crate::shared::domain::DomainError;
use crate::shared::persistence::db::models::ReportContextModel;
use crate::shared::persistence::db::schema::report_context;

#[derive(Clone)]
pub struct ReportContextRepository {}

impl ReportContextRepository {
    pub fn new(_pool: DbPool) -> Self {
        Self {}
    }

    pub fn insert_all(
        &self,
        conn: &mut DbConnection,
        report_id: i32,
        pairs: &[(i32, i32)],
    ) -> Result<(), DomainError> {
        if pairs.is_empty() {
            return Ok(());
        }
        let rows: Vec<ReportContextModel> = pairs
            .iter()
            .map(|(key_id, value_id)| ReportContextModel {
                report_id,
                key_id: *key_id,
                value_id: *value_id,
            })
            .collect();
        diesel::insert_into(report_context::table)
            .values(&rows)
            .on_conflict((report_context::report_id, report_context::key_id))
            .do_nothing()
            .execute(conn)
            .map_err(|e| DomainError::Database(e.to_string()))?;
        Ok(())
    }
}
