import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import {
    Upload, FileText, CheckCircle, AlertTriangle,
    Edit2, X, Save, Trash2, Eye, ArrowLeft,
    Terminal, RefreshCw, ChevronDown, ChevronUp,
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/*  Editor view — shown when a dictionary file is opened for editing  */
/* ------------------------------------------------------------------ */
const DictionaryEditor = ({ filename, onClose }) => {
    const queryClient = useQueryClient();
    const [content, setContent] = useState('');
    const [saved, setSaved] = useState(false);
    const [error, setError] = useState(null);
    const [dirty, setDirty] = useState(false);

    // Fetch file content
    const { data, isLoading } = useQuery({
        queryKey: ['dictionary', 'content', filename],
        queryFn: () => api.get(`/dictionary/content/${encodeURIComponent(filename)}`).then(r => r.data),
        refetchOnWindowFocus: false,
    });

    useEffect(() => {
        if (data?.content != null) {
            setContent(data.content);
            setDirty(false);
        }
    }, [data]);

    const saveMutation = useMutation({
        mutationFn: () => api.put(`/dictionary/content/${encodeURIComponent(filename)}`, { content }),
        onSuccess: (res) => {
            queryClient.invalidateQueries(['dictionary']);
            setSaved(true);
            setDirty(false);
            setError(null);
            setTimeout(() => setSaved(false), 4000);
        },
        onError: (err) => {
            setError(err.response?.data?.detail || 'Save failed');
            setSaved(false);
        },
    });

    const handleKeyDown = (e) => {
        // Ctrl+S / Cmd+S to save
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            saveMutation.mutate();
        }
        // Tab inserts a real tab instead of moving focus
        if (e.key === 'Tab') {
            e.preventDefault();
            const ta = e.target;
            const start = ta.selectionStart;
            const end = ta.selectionEnd;
            const val = ta.value;
            const newVal = val.substring(0, start) + '\t' + val.substring(end);
            setContent(newVal);
            setDirty(true);
            requestAnimationFrame(() => {
                ta.selectionStart = ta.selectionEnd = start + 1;
            });
        }
    };

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <button onClick={onClose}
                    className="flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-indigo-600 transition-colors">
                    <ArrowLeft size={16} /> Back to list
                </button>
                <div className="flex items-center gap-3">
                    {dirty && (
                        <span className="text-xs font-bold text-amber-500 bg-amber-50 px-3 py-1 rounded-full border border-amber-200">
                            Unsaved changes
                        </span>
                    )}
                    <button
                        onClick={() => saveMutation.mutate()}
                        disabled={saveMutation.isPending || !dirty}
                        className={`flex items-center gap-2 px-5 py-2 rounded-xl font-bold text-white shadow-md transition-all
                            ${saveMutation.isPending || !dirty
                                ? 'bg-slate-300 cursor-not-allowed'
                                : 'bg-indigo-600 hover:bg-indigo-700 active:scale-95'}`}
                    >
                        <Save size={16} />
                        {saveMutation.isPending ? 'Saving...' : 'Save'}
                    </button>
                </div>
            </div>

            {/* Title */}
            <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200">
                <div className="flex items-center gap-3 mb-1">
                    <FileText size={20} className="text-indigo-500" />
                    <h3 className="text-lg font-extrabold text-slate-800">{filename}</h3>
                </div>
                <p className="text-xs text-slate-400 ml-8">
                    Ctrl+S to save &middot; Tab inserts a tab character &middot;
                    FreeRADIUS 4.x types (uint32, uint16...) are auto-converted on save
                </p>
            </div>

            {/* Feedback */}
            {(error || saved) && (
                <div className={`p-4 rounded-xl flex items-center gap-3 border animate-fadeIn ${error ? 'bg-red-50 text-red-700 border-red-100' : 'bg-emerald-50 text-emerald-700 border-emerald-100'}`}>
                    {error ? <AlertTriangle size={18} /> : <CheckCircle size={18} />}
                    <span className="text-sm font-medium">{error || 'Saved successfully.'}</span>
                    <button onClick={() => { setError(null); setSaved(false); }} className="ml-auto text-slate-400 hover:text-slate-600"><X size={16} /></button>
                </div>
            )}

            {/* Editor */}
            {isLoading ? (
                <div className="text-center py-20 text-slate-400 font-bold">Loading content...</div>
            ) : (
                <textarea
                    value={content}
                    onChange={(e) => { setContent(e.target.value); setDirty(true); setError(null); }}
                    onKeyDown={handleKeyDown}
                    spellCheck={false}
                    className="w-full min-h-[520px] bg-slate-900 text-green-300 font-mono text-sm p-5 rounded-2xl border border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-y leading-relaxed"
                />
            )}
        </div>
    );
};

/* ------------------------------------------------------------------ */
/*  FreeRADIUS log panel                                               */
/* ------------------------------------------------------------------ */
const RadiusLogPanel = () => {
    const [expanded, setExpanded] = useState(false);

    const { data, isLoading, refetch, isFetching } = useQuery({
        queryKey: ['dictionary', 'radius-logs'],
        queryFn: () => api.get('/dictionary/radius-logs').then(r => r.data),
        refetchOnWindowFocus: false,
        enabled: expanded,
    });

    const statusColors = {
        running: 'bg-emerald-500',
        error: 'bg-red-500',
        unknown: 'bg-amber-500',
        unavailable: 'bg-slate-400',
    };

    const statusLabels = {
        running: 'Running',
        error: 'Error',
        unknown: 'Unknown',
        unavailable: 'Unavailable',
    };

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-center justify-between p-5 hover:bg-slate-50 transition-colors"
            >
                <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-slate-800 rounded-xl text-green-400">
                        <Terminal size={20} />
                    </div>
                    <div className="text-left">
                        <h3 className="text-base font-bold text-slate-800">FreeRADIUS Logs</h3>
                        <p className="text-xs text-slate-400">Dictionary loading diagnostics</p>
                    </div>
                    {data && (
                        <div className="flex items-center gap-2 ml-3">
                            <span className={`w-2.5 h-2.5 rounded-full ${statusColors[data.status] || statusColors.unknown} ${data.status === 'running' ? 'animate-pulse' : ''}`} />
                            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                                {statusLabels[data.status] || data.status}
                            </span>
                        </div>
                    )}
                </div>
                {expanded ? <ChevronUp size={20} className="text-slate-400" /> : <ChevronDown size={20} className="text-slate-400" />}
            </button>

            {expanded && (
                <div className="border-t border-slate-100">
                    <div className="flex items-center justify-between px-5 py-3 bg-slate-50">
                        <span className="text-xs text-slate-400 font-medium">
                            {data ? `${data.filtered_lines} relevant lines of ${data.total_lines} total` : 'Loading...'}
                        </span>
                        <button
                            onClick={() => refetch()}
                            disabled={isFetching}
                            className="flex items-center gap-1.5 text-xs font-bold text-indigo-600 hover:text-indigo-700 disabled:text-slate-400 transition-colors"
                        >
                            <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
                            Refresh
                        </button>
                    </div>
                    <div className="bg-slate-900 max-h-72 overflow-y-auto p-4 font-mono text-xs leading-relaxed">
                        {isLoading ? (
                            <div className="text-slate-500 text-center py-6">Loading logs...</div>
                        ) : data?.logs?.length > 0 ? (
                            data.logs.map((line, i) => {
                                const isError = /error|duplicate|fail/i.test(line);
                                const isWarning = /warning|skip/i.test(line);
                                const isSuccess = /ready to process|listening on/i.test(line);
                                return (
                                    <div key={i} className={`py-0.5 ${
                                        isError ? 'text-red-400' :
                                        isWarning ? 'text-amber-400' :
                                        isSuccess ? 'text-emerald-400' :
                                        'text-slate-400'
                                    }`}>
                                        {line}
                                    </div>
                                );
                            })
                        ) : (
                            <div className="text-slate-500 text-center py-6">No dictionary-related log lines found.</div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */
const DictionariesPage = () => {
    const queryClient = useQueryClient();
    const [uploadError, setUploadError] = useState(null);
    const [uploadSuccess, setUploadSuccess] = useState(null);
    const [renamingFile, setRenamingFile] = useState(null);
    const [newName, setNewName] = useState('');
    const [editingFile, setEditingFile] = useState(null);
    const [confirmDelete, setConfirmDelete] = useState(null);

    const { data: files } = useQuery({
        queryKey: ['dictionary', 'files'],
        queryFn: () => api.get('/dictionary/files').then(r => r.data),
    });

    /* Upload */
    const uploadMutation = useMutation({
        mutationFn: (formData) => api.post('/dictionary/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        }),
        onSuccess: (data) => {
            queryClient.invalidateQueries(['dictionary']);
            setUploadSuccess(data.data.message);
            setUploadError(null);
            setTimeout(() => setUploadSuccess(null), 6000);
        },
        onError: (err) => {
            setUploadError(err.response?.data?.detail || 'Upload failed');
            setUploadSuccess(null);
        },
    });

    /* Rename */
    const renameMutation = useMutation({
        mutationFn: ({ oldName, newName: nn }) => api.post(`/dictionary/rename?old_name=${encodeURIComponent(oldName)}&new_name=${encodeURIComponent(nn)}`),
        onSuccess: () => {
            queryClient.invalidateQueries(['dictionary']);
            setRenamingFile(null);
            setNewName('');
            setUploadSuccess('Dictionary renamed successfully.');
            setTimeout(() => setUploadSuccess(null), 3000);
        },
        onError: (err) => {
            setUploadError(err.response?.data?.detail || 'Rename failed');
            setRenamingFile(null);
        },
    });

    /* Delete */
    const deleteMutation = useMutation({
        mutationFn: (fname) => api.delete(`/dictionary/${encodeURIComponent(fname)}`),
        onSuccess: (_, fname) => {
            queryClient.invalidateQueries(['dictionary']);
            setConfirmDelete(null);
            setUploadSuccess(`Dictionary ${fname} deleted.`);
            setTimeout(() => setUploadSuccess(null), 3000);
        },
        onError: (err) => {
            setUploadError(err.response?.data?.detail || 'Delete failed');
            setConfirmDelete(null);
        },
    });

    const handleFileChange = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append('file', file);
        setUploadError(null);
        setUploadSuccess(null);
        uploadMutation.mutate(formData);
        // Reset file input so the same file can be re-uploaded
        e.target.value = '';
    };

    /* ------- If editing a file, show the editor ------- */
    if (editingFile) {
        return (
            <div className="max-w-7xl mx-auto space-y-6">
                <DictionaryEditor
                    filename={editingFile}
                    onClose={() => setEditingFile(null)}
                />
            </div>
        );
    }

    /* ------- Normal list view ------- */
    return (
        <div className="space-y-6 max-w-7xl mx-auto">
            {/* Page header */}
            <div>
                <h2 className="text-3xl font-extrabold text-slate-800 tracking-tight">Dictionary Manager</h2>
                <p className="text-slate-500">Upload, edit, rename and delete RADIUS vendor dictionaries.</p>
            </div>

            {/* Upload card */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-indigo-50 rounded-xl text-indigo-600">
                            <Upload size={24} />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-slate-800">Upload Dictionary</h3>
                            <p className="text-sm text-slate-500">
                                FreeRADIUS 4.x types (uint32, uint16...) are auto-converted on upload.
                            </p>
                        </div>
                    </div>
                    <div>
                        <input type="file" id="dict-upload" className="hidden" onChange={handleFileChange} />
                        <label
                            htmlFor="dict-upload"
                            className={`flex items-center gap-2 px-6 py-2.5 rounded-xl cursor-pointer transition-all font-bold text-white shadow-md
                                ${uploadMutation.isPending ? 'bg-slate-400' : 'bg-indigo-600 hover:bg-indigo-700 hover:shadow-lg active:scale-95'}`}
                        >
                            {uploadMutation.isPending ? 'Validating...' : 'Upload File'}
                        </label>
                    </div>
                </div>

                {(uploadError || uploadSuccess) && (
                    <div className={`p-4 rounded-xl flex items-center gap-3 border animate-fadeIn ${uploadError ? 'bg-red-50 text-red-700 border-red-100' : 'bg-emerald-50 text-emerald-700 border-emerald-100'}`}>
                        {uploadError ? <AlertTriangle size={20} /> : <CheckCircle size={20} />}
                        <div className="text-sm font-medium flex-1">{uploadError || uploadSuccess}</div>
                        <button onClick={() => { setUploadError(null); setUploadSuccess(null); }} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
                    </div>
                )}
            </div>

            {/* FreeRADIUS Log Panel */}
            <RadiusLogPanel />

            {/* File grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {files?.map(file => (
                    <div key={file} className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 hover:border-indigo-300 transition-all group flex flex-col justify-between min-h-[160px]">
                        {/* Top row */}
                        <div className="flex items-start justify-between gap-3">
                            <div className="flex items-center gap-3 min-w-0 flex-1">
                                <div className="p-3 bg-slate-50 rounded-xl text-slate-400 group-hover:bg-indigo-50 group-hover:text-indigo-500 transition-colors shrink-0">
                                    <FileText size={24} />
                                </div>

                                {renamingFile === file ? (
                                    <div className="flex flex-col gap-2 flex-1">
                                        <input
                                            autoFocus
                                            className="w-full border-2 border-indigo-500 rounded-lg px-3 py-1.5 text-sm font-bold outline-none shadow-sm"
                                            value={newName}
                                            onChange={(e) => setNewName(e.target.value)}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') renameMutation.mutate({ oldName: file, newName });
                                                if (e.key === 'Escape') setRenamingFile(null);
                                            }}
                                        />
                                        <div className="flex gap-2">
                                            <button onClick={() => renameMutation.mutate({ oldName: file, newName })} className="flex-1 bg-indigo-600 text-white text-xs py-1 rounded-md font-bold flex items-center justify-center gap-1 hover:bg-indigo-700">
                                                <Save size={12} /> Save
                                            </button>
                                            <button onClick={() => setRenamingFile(null)} className="flex-1 bg-slate-100 text-slate-500 text-xs py-1 rounded-md font-bold flex items-center justify-center gap-1 hover:bg-slate-200">
                                                <X size={12} /> Cancel
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="min-w-0">
                                        <h4 className="font-bold text-slate-800 truncate text-base" title={file}>{file}</h4>
                                        <div className="flex items-center gap-2 mt-1">
                                            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                            <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Active</span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Bottom action bar */}
                        {renamingFile !== file && confirmDelete !== file && (
                            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-end gap-1">
                                <button onClick={() => setEditingFile(file)} title="View / Edit content"
                                    className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all">
                                    <Eye size={18} />
                                </button>
                                <button onClick={() => { setRenamingFile(file); setNewName(file); }} title="Rename"
                                    className="p-2 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-all">
                                    <Edit2 size={18} />
                                </button>
                                <button onClick={() => setConfirmDelete(file)} title="Delete"
                                    className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all">
                                    <Trash2 size={18} />
                                </button>
                            </div>
                        )}

                        {/* Delete confirmation */}
                        {confirmDelete === file && (
                            <div className="mt-4 pt-3 border-t border-red-100 flex items-center justify-between">
                                <span className="text-xs font-bold text-red-600">Delete this dictionary?</span>
                                <div className="flex gap-2">
                                    <button onClick={() => deleteMutation.mutate(file)}
                                        className="px-3 py-1 bg-red-600 text-white text-xs rounded-lg font-bold hover:bg-red-700 transition-colors">
                                        Yes, delete
                                    </button>
                                    <button onClick={() => setConfirmDelete(null)}
                                        className="px-3 py-1 bg-slate-100 text-slate-600 text-xs rounded-lg font-bold hover:bg-slate-200 transition-colors">
                                        Cancel
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {/* Empty state */}
            {files?.length === 0 && (
                <div className="flex flex-col items-center justify-center py-20 bg-slate-50 rounded-3xl border-2 border-dashed border-slate-200">
                    <div className="p-6 bg-white rounded-full shadow-lg text-slate-300 mb-4">
                        <FileText size={48} />
                    </div>
                    <h3 className="text-xl font-bold text-slate-800">No Custom Dictionaries</h3>
                    <p className="text-slate-500 max-w-sm text-center mt-2">
                        Upload a vendor dictionary file to expand RADIUS attribute support.
                    </p>
                </div>
            )}
        </div>
    );
};

export default DictionariesPage;
