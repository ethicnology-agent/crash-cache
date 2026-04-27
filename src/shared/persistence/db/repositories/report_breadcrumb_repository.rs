use super::{DbConnection, DbPool};
use diesel::prelude::*;

use crate::shared::domain::DomainError;
use crate::shared::persistence::db::models::ReportBreadcrumbModel;
use crate::shared::persistence::db::schema::report_breadcrumb;

#[derive(Clone)]
pub struct ReportBreadcrumbRepository {}

impl ReportBreadcrumbRepository {
    pub fn new(_pool: DbPool) -> Self {
        Self {}
    }

    pub fn insert_all(
        &self,
        conn: &mut DbConnection,
        report_id: i32,
        breadcrumb_ids: &[i32],
    ) -> Result<(), DomainError> {
        if breadcrumb_ids.is_empty() {
            return Ok(());
        }
        let rows: Vec<ReportBreadcrumbModel> = breadcrumb_ids
            .iter()
            .enumerate()
            .map(|(seq, breadcrumb_id)| ReportBreadcrumbModel {
                report_id,
                seq: seq as i32,
                breadcrumb_id: *breadcrumb_id,
            })
            .collect();
        diesel::insert_into(report_breadcrumb::table)
            .values(&rows)
            .on_conflict((report_breadcrumb::report_id, report_breadcrumb::seq))
            .do_nothing()
            .execute(conn)
            .map_err(|e| DomainError::Database(e.to_string()))?;
        Ok(())
    }
}
