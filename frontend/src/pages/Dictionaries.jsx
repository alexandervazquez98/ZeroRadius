import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { Upload, FileText, CheckCircle, AlertTriangle, Edit2, X, Save } from 'lucide-react';

const DictionariesPage = () => {
    const queryClient = useQueryClient();
    const [uploadError, setUploadError] = useState(null);
    const [uploadSuccess, setUploadSuccess] = useState(null);
    const [renamingFile, setRenamingFile] = useState(null);
    const [newName, setNewName] = useState("");

    const { data: files } = useQuery({
        queryKey: ['dictionary', 'files'],
        queryFn: () => api.get('/dictionary/files').then(r => r.data)
    });

    const uploadMutation = useMutation({
        mutationFn: (formData) => api.post('/dictionary/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        }),
        onSuccess: (data) => {
            queryClient.invalidateQueries(['dictionary']);
            queryClient.invalidateQueries(['dictionary', 'files']);
            queryClient.invalidateQueries(['dictionary', 'attributes']);
            setUploadSuccess(data.data.message);
            setUploadError(null);
            setTimeout(() => setUploadSuccess(null), 5000);
        },
        onError: (err) => {
            setUploadError(err.response?.data?.detail || "Upload failed");
            setUploadSuccess(null);
        }
    });

    const renameMutation = useMutation({
        mutationFn: ({ oldName, newName }) => api.post(`/dictionary/rename?old_name=${oldName}&new_name=${newName}`),
        onSuccess: () => {
            queryClient.invalidateQueries(['dictionary', 'files']);
            queryClient.invalidateQueries(['dictionary', 'attributes']);
            setRenamingFile(null);
            setNewName("");
            setUploadSuccess("Dictionary renamed successfully");
            setTimeout(() => setUploadSuccess(null), 3000);
        },
        onError: (err) => {
            setUploadError(err.response?.data?.detail || "Rename failed");
            setRenamingFile(null);
        }
    });

    const handleFileChange = (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        setUploadError(null);
        setUploadSuccess(null);
        uploadMutation.mutate(formData);
    };

    const startRename = (file) => {
        setRenamingFile(file);
        setNewName(file);
    };

    return (
        <div className="space-y-6 max-w-7xl mx-auto">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-3xl font-extrabold text-slate-800 tracking-tight">Dictionary Manager</h2>
                    <p className="text-slate-500">Manage and rename RADIUS vendor dictionaries.</p>
                </div>
            </div>

            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-indigo-50 rounded-xl text-indigo-600">
                            <Upload size={24} />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-slate-800">New Dictionary</h3>
                            <p className="text-sm text-slate-500">Add a new .txt dictionary file to the system.</p>
                        </div>
                    </div>
                    <div>
                        <input
                            type="file"
                            id="dict-upload"
                            className="hidden"
                            onChange={handleFileChange}
                        />
                        <label
                            htmlFor="dict-upload"
                            className={`flex items-center gap-2 px-6 py-2.5 rounded-xl cursor-pointer transition-all font-bold text-white shadow-md ${uploadMutation.isPending ? 'bg-slate-400' : 'bg-indigo-600 hover:bg-indigo-700 hover:shadow-lg active:scale-95'}`}
                        >
                            {uploadMutation.isPending ? 'Validating...' : 'Upload File'}
                        </label>
                    </div>
                </div>

                {(uploadError || uploadSuccess) && (
                    <div className={`p-4 rounded-xl flex items-center gap-3 border animate-fadeIn ${uploadError ? 'bg-red-50 text-red-700 border-red-100' : 'bg-emerald-50 text-emerald-700 border-emerald-100'}`}>
                        {uploadError ? <AlertTriangle size={20} /> : <CheckCircle size={20} />}
                        <div className="text-sm font-medium">{uploadError || uploadSuccess}</div>
                    </div>
                )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {files?.map(file => (
                    <div key={file} className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 hover:border-indigo-300 transition-all group flex flex-col justify-between h-40">
                        <div className="flex items-start justify-between gap-4">
                            <div className="flex items-center gap-4 min-w-0">
                                <div className="p-3 bg-slate-50 rounded-xl text-slate-400 group-hover:bg-indigo-50 group-hover:text-indigo-500 transition-colors">
                                    <FileText size={28} />
                                </div>
                                <div className="min-w-0 flex-1">
                                    {renamingFile === file ? (
                                        <div className="flex flex-col gap-2">
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
                                                <button onClick={() => renameMutation.mutate({ oldName: file, newName })} className="flex-1 bg-indigo-600 text-white text-xs py-1 rounded-md font-bold flex items-center justify-center gap-1 hover:bg-indigo-700"><Save size={12} /> Save</button>
                                                <button onClick={() => setRenamingFile(null)} className="flex-1 bg-slate-100 text-slate-500 text-xs py-1 rounded-md font-bold flex items-center justify-center gap-1 hover:bg-slate-200"><X size={12} /> Cancel</button>
                                            </div>
                                        </div>
                                    ) : (
                                        <>
                                            <h4 className="font-bold text-slate-800 truncate text-lg" title={file}>{file}</h4>
                                            <div className="flex items-center gap-2">
                                                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                                                <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Active</span>
                                            </div>
                                        </>
                                    )}
                                </div>
                            </div>

                            {renamingFile !== file && (
                                <button
                                    onClick={() => startRename(file)}
                                    className="p-2 text-slate-300 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all"
                                    title="Rename Dictionary"
                                >
                                    <Edit2 size={20} />
                                </button>
                            )}
                        </div>

                        {!renamingFile && (
                            <div className="mt-4 pt-4 border-t border-slate-50 flex items-center justify-between">
                                <span className="text-[10px] font-black text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full uppercase tracking-tighter shadow-sm border border-emerald-100">
                                    ✓ Fully Loaded
                                </span>
                                <span className="text-[10px] font-bold text-slate-300">Attributes Tracked</span>
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {files?.length === 0 && (
                <div className="flex flex-col items-center justify-center py-20 bg-slate-50 rounded-3xl border-2 border-dashed border-slate-200">
                    <div className="p-6 bg-white rounded-full shadow-lg text-slate-300 mb-4">
                        <FileText size={48} />
                    </div>
                    <h3 className="text-xl font-bold text-slate-800">No Custom Dictionaries</h3>
                    <p className="text-slate-500 max-w-sm text-center mt-2">The system is currently running on the core internal dictionary. Upload a vendor file to expand support.</p>
                </div>
            )}
        </div>
    );
};

export default DictionariesPage;
